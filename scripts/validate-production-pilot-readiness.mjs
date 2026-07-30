#!/usr/bin/env node
import { existsSync } from "node:fs";
import { basename } from "node:path";
import {
  parseArgs,
  readJson,
  resolveRepoPath,
  safeRelative,
  utcTimestamp,
  validateImageRef,
  validateWidgetRelease,
  writeJson,
} from "./azure-release-lib.mjs";

const args = parseArgs(process.argv.slice(2));
const positional = args._ ?? [];

const manifestPath = resolveRepoPath(String(args.manifest ?? positional[0] ?? "artifacts/deployment-release/manifest.json"));
const releaseDir = resolveRepoPath(String(args["release-dir"] ?? positional[1] ?? "artifacts/widget-release"));
const stagingReportPath = resolveRepoPath(String(args["staging-report"] ?? positional[2] ?? "artifacts/azure-staging-validation/report.json"));
const browserSmokePath = resolveRepoPath(String(args["browser-smoke"] ?? positional[3] ?? "artifacts/azure-staging-validation/browser-smoke.json"));
const telemetryPath = resolveRepoPath(String(args.telemetry ?? positional[4] ?? "artifacts/azure-staging-validation/telemetry.json"));
const alertsPath = resolveRepoPath(String(args.alerts ?? positional[5] ?? "artifacts/azure-staging-validation/alerts.json"));
const rollbackPath = resolveRepoPath(String(args.rollback ?? positional[6] ?? "artifacts/azure-staging-validation/rollback.json"));
const manualGatePath = resolveRepoPath(String(args["manual-gate"] ?? positional[7] ?? "artifacts/production-pilot-readiness/manual-gate.json"));
const outPath = resolveRepoPath(String(args.out ?? positional[9] ?? "artifacts/production-pilot-readiness/report.json"));
const approvalNote = String(args["approval-note"] ?? process.env.PILOT_APPROVAL_NOTE ?? positional[8] ?? "").trim();

const failures = [];
const gates = [];

function gate(id, passed, evidence) {
  gates.push({ id, status: passed ? "passed" : "failed", evidence });
  if (!passed) failures.push(id);
}

function readEvidence(path, label) {
  if (!existsSync(path)) {
    return { missing: true, label, path: safeRelative(path) };
  }
  try {
    return readJson(path);
  } catch (error) {
    return { invalid: true, label, path: safeRelative(path), error: error.message };
  }
}

function statusOf(report) {
  return String(report?.overall_status ?? report?.status ?? report?.classification ?? "").toLowerCase();
}

function isPassed(report) {
  const status = statusOf(report);
  return ["passed", "validated", "success", "succeeded", "healthy", "completed"].includes(status)
    || status.includes("validated and ready");
}

function hasNoCriticalBlockers(report) {
  const blockers = [
    ...(Array.isArray(report?.critical_blockers) ? report.critical_blockers : []),
    ...(Array.isArray(report?.blockers) ? report.blockers : []),
    ...(Array.isArray(report?.warnings) ? report.warnings.filter((warning) => String(warning).toLowerCase().includes("critical")) : []),
  ];
  return blockers.length === 0;
}

function passField(report, names) {
  return names.some((name) => report?.[name] === true || statusOf(report?.[name]) === "passed");
}

const manifest = readEvidence(manifestPath, "deployment manifest");
if (manifest.missing || manifest.invalid) {
  gate("deployment_manifest_present", false, manifest);
} else {
  gate("staging_release_manifest", manifest.schema_version === "1.0" && manifest.environment === "staging", {
    path: safeRelative(manifestPath),
    environment: manifest.environment,
    release_id: manifest.release_id,
  });
  try {
    validateImageRef(manifest.api_image?.ref, "API image ref");
    validateImageRef(manifest.web_image?.ref, "Web image ref");
    gate("immutable_image_refs", true, {
      api_image: manifest.api_image?.ref,
      web_image: manifest.web_image?.ref,
    });
  } catch (error) {
    gate("immutable_image_refs", false, { error: error.message });
  }
  for (const name of ["admin_readiness", "pilot_verification", "pilot_readiness"]) {
    gate(`manifest_${name}`, manifest.gates?.[name] === "passed", {
      value: manifest.gates?.[name] ?? "missing",
    });
  }
}

if (existsSync(releaseDir)) {
  try {
    const { manifest: widgetManifest } = validateWidgetRelease(releaseDir);
    gate("widget_release_integrity", widgetManifest.sdk_version === manifest.widget_release?.sdk_version, {
      release_dir: safeRelative(releaseDir),
      sdk_version: widgetManifest.sdk_version,
    });
  } catch (error) {
    gate("widget_release_integrity", false, { error: error.message });
  }
} else {
  gate("widget_release_integrity", false, { release_dir: safeRelative(releaseDir), missing: true });
}

const stagingReport = readEvidence(stagingReportPath, "staging validation report");
gate("b4_staging_validation_passed", isPassed(stagingReport) && hasNoCriticalBlockers(stagingReport), {
  path: safeRelative(stagingReportPath),
  status: statusOf(stagingReport) || "missing",
});

const browserSmoke = readEvidence(browserSmokePath, "staging browser smoke");
gate("live_browser_and_tenant_isolation", isPassed(browserSmoke) && hasNoCriticalBlockers(browserSmoke), {
  path: safeRelative(browserSmokePath),
  status: statusOf(browserSmoke) || "missing",
});

const telemetry = readEvidence(telemetryPath, "staging telemetry validation");
gate("telemetry_privacy_and_correlation", isPassed(telemetry) && hasNoCriticalBlockers(telemetry), {
  path: safeRelative(telemetryPath),
  status: statusOf(telemetry) || "missing",
});

const alerts = readEvidence(alertsPath, "staging alert validation");
gate("alert_routing_validated", isPassed(alerts) && hasNoCriticalBlockers(alerts), {
  path: safeRelative(alertsPath),
  status: statusOf(alerts) || "missing",
});

const rollback = readEvidence(rollbackPath, "staging rollback drill");
gate("rollback_drill_validated", isPassed(rollback) && hasNoCriticalBlockers(rollback), {
  path: safeRelative(rollbackPath),
  status: statusOf(rollback) || "missing",
});

const manualGate = readEvidence(manualGatePath, "manual production-pilot gate");
if (manualGate.missing || manualGate.invalid) {
  gate("manual_gate_present", false, manualGate);
} else {
  gate("manual_accessibility_review", passField(manualGate, ["manual_accessibility_review_passed", "accessibility_review_passed"]), {
    path: safeRelative(manualGatePath),
  });
  gate("manual_security_review", passField(manualGate, ["manual_security_review_passed", "security_review_passed"]), {
    path: safeRelative(manualGatePath),
  });
  gate("production_domain_plan_reviewed", manualGate.production_domain_plan_reviewed === true, {});
  gate("rollback_operator_ready", manualGate.rollback_operator_ready === true, {});
  gate("support_contact_ready", manualGate.support_contact_ready === true, {});
  gate("first_pilot_tenant_approved", manualGate.first_pilot_tenant_approved === true, {});
  gate("no_customer_data_in_validation", manualGate.no_customer_data_in_validation === true, {});
  gate("manual_gate_has_approver", Boolean(String(manualGate.approved_by ?? "").trim()), {
    approved_at: manualGate.approved_at ?? null,
  });
}

gate("approval_note_present", approvalNote.length >= 12, {
  length: approvalNote.length,
});

const report = {
  schema_version: "1.0",
  generated_at: utcTimestamp(),
  source: basename(import.meta.url),
  release_id: manifest.release_id ?? null,
  git_sha: manifest.git_sha ?? null,
  manifest: existsSync(manifestPath) ? safeRelative(manifestPath) : null,
  evidence: {
    staging_report: safeRelative(stagingReportPath),
    browser_smoke: safeRelative(browserSmokePath),
    telemetry: safeRelative(telemetryPath),
    alerts: safeRelative(alertsPath),
    rollback: safeRelative(rollbackPath),
    manual_gate: safeRelative(manualGatePath),
  },
  gates,
  overall_status: failures.length === 0 ? "passed" : "blocked",
  classification: failures.length === 0
    ? "production-pilot promotion gate passed"
    : "production-pilot promotion blocked",
};

writeJson(outPath, report);

if (failures.length > 0) {
  console.error("Production-pilot readiness failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  console.error(`Report: ${safeRelative(outPath)}`);
  process.exit(1);
}

console.log(JSON.stringify({
  status: "passed",
  report: safeRelative(outPath),
  release_id: report.release_id,
  git_sha: report.git_sha,
}, null, 2));
