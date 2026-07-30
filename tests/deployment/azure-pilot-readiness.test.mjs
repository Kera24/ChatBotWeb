import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";

const root = process.cwd();
const fixtureRoot = join(root, "artifacts/test-azure-pilot-readiness");

function run(args, options = {}) {
  return spawnSync(process.execPath, args, {
    cwd: root,
    encoding: "utf8",
    ...options,
  });
}

function sha(value) {
  return createHash("sha256").update(value).digest("hex");
}

function write(path, value) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, value, "utf8");
}

function json(path, value) {
  write(path, `${JSON.stringify(value, null, 2)}\n`);
}

function fixtureRelease() {
  const release = join(fixtureRoot, "widget-release");
  const loader = "console.log('loader');\n";
  const html = "<html><body><script src=\"/assets/index-AbCd1234.js\"></script></body></html>\n";
  const js = "console.log('widget');\n";
  write(join(release, "sdk/v0.1.0-foundation.0/loader.js"), loader);
  write(join(release, "sdk/v1/loader.js"), loader);
  write(join(release, "widget/index.html"), html);
  write(join(release, "widget/assets/index-AbCd1234.js"), js);
  json(join(release, "manifest.json"), {
    schema_version: 1,
    release_channel: "pilot",
    release_environment: "staging",
    sdk_version: "0.1.0-foundation.0",
    sdk_major: 1,
    protocol_major: 1,
    api_version: "v1",
    checksums: {
      immutable_loader_sha256: sha(loader),
      major_alias_loader_sha256: sha(loader),
      iframe_html_sha256: sha(html),
    },
    cache_policies: {
      immutable_sdk: "public, max-age=31536000, immutable",
      sdk_major_alias: "public, max-age=300, must-revalidate",
      iframe_html: "no-cache",
      iframe_hashed_assets: "public, max-age=31536000, immutable",
    },
  });
  return release;
}

function fixtureEvidence(overrides = {}) {
  rmSync(fixtureRoot, { recursive: true, force: true });
  const release = fixtureRelease();
  const manifest = join(fixtureRoot, "deployment-release/manifest.json");
  const evidence = join(fixtureRoot, "azure-staging-validation");
  const manual = join(fixtureRoot, "production-pilot-readiness/manual-gate.json");
  json(manifest, {
    schema_version: "1.0",
    release_id: "release-fixture",
    environment: "staging",
    git_sha: "abcdef123456",
    protocol_major: 1,
    public_api_version: "v1",
    db_migration_head: "0012_widget_knowledge_preview_installation",
    api_image: { ref: "example.azurecr.io/chatbotweb-api@sha256:aaaaaaaa", digest: "aaaaaaaa" },
    web_image: { ref: "example.azurecr.io/chatbotweb-web@sha256:bbbbbbbb", digest: "bbbbbbbb" },
    widget_release: {
      sdk_version: "0.1.0-foundation.0",
      sdk_immutable_loader_sha256: sha("console.log('loader');\n"),
      iframe_html_sha256: sha("<html><body><script src=\"/assets/index-AbCd1234.js\"></script></body></html>\n"),
    },
    gates: {
      admin_readiness: "passed",
      pilot_verification: "passed",
      pilot_readiness: "passed",
    },
    ...(overrides.manifest ?? {}),
  });
  for (const name of ["report", "browser-smoke", "telemetry", "alerts", "rollback"]) {
    json(join(evidence, `${name}.json`), {
      schema_version: "1.0",
      overall_status: "passed",
      critical_blockers: [],
      ...(overrides[name] ?? {}),
    });
  }
  json(manual, {
    schema_version: "1.0",
    approved_by: "operator",
    approved_at: "2026-07-30T00:00:00.000Z",
    manual_accessibility_review_passed: true,
    manual_security_review_passed: true,
    production_domain_plan_reviewed: true,
    rollback_operator_ready: true,
    support_contact_ready: true,
    first_pilot_tenant_approved: true,
    no_customer_data_in_validation: true,
    ...(overrides.manual ?? {}),
  });
  return { manifest, release, evidence, manual, out: join(fixtureRoot, "production-pilot-readiness/report.json") };
}

function readinessArgs(fixture) {
  return [
    "scripts/validate-production-pilot-readiness.mjs",
    "--manifest", fixture.manifest,
    "--release-dir", fixture.release,
    "--staging-report", join(fixture.evidence, "report.json"),
    "--browser-smoke", join(fixture.evidence, "browser-smoke.json"),
    "--telemetry", join(fixture.evidence, "telemetry.json"),
    "--alerts", join(fixture.evidence, "alerts.json"),
    "--rollback", join(fixture.evidence, "rollback.json"),
    "--manual-gate", fixture.manual,
    "--approval-note", "Approved for controlled pilot promotion.",
    "--out", fixture.out,
  ];
}

test("production-pilot readiness passes with staged release, B4 evidence, rollback, telemetry, alerts, and manual gate", () => {
  const fixture = fixtureEvidence();
  const result = run(readinessArgs(fixture));
  assert.equal(result.status, 0, result.stderr || result.stdout);
  const report = JSON.parse(readFileSync(fixture.out, "utf8"));
  assert.equal(report.overall_status, "passed");
  assert.equal(report.classification, "production-pilot promotion gate passed");
});

test("production-pilot readiness accepts positional arguments for Windows npm compatibility", () => {
  const fixture = fixtureEvidence();
  const out = join(fixtureRoot, "production-pilot-readiness/positional-report.json");
  const result = run([
    "scripts/validate-production-pilot-readiness.mjs",
    fixture.manifest,
    fixture.release,
    join(fixture.evidence, "report.json"),
    join(fixture.evidence, "browser-smoke.json"),
    join(fixture.evidence, "telemetry.json"),
    join(fixture.evidence, "alerts.json"),
    join(fixture.evidence, "rollback.json"),
    fixture.manual,
    "Approved for controlled pilot promotion.",
    out,
  ]);
  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.equal(JSON.parse(readFileSync(out, "utf8")).overall_status, "passed");
});
test("production-pilot readiness blocks without successful live staging evidence", () => {
  const fixture = fixtureEvidence({ "browser-smoke": { overall_status: "failed", critical_blockers: ["tenant isolation failed"] } });
  const result = run(readinessArgs(fixture));
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /live_browser_and_tenant_isolation/);
  const report = JSON.parse(readFileSync(fixture.out, "utf8"));
  assert.equal(report.overall_status, "blocked");
});

test("production-pilot readiness blocks when manual accessibility or security review is absent", () => {
  const fixture = fixtureEvidence({
    manual: {
      manual_accessibility_review_passed: false,
      manual_security_review_passed: false,
    },
  });
  const result = run(readinessArgs(fixture));
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /manual_accessibility_review/);
  assert.match(result.stderr, /manual_security_review/);
});

test("production-pilot readiness report does not copy approval note or secret-like evidence", () => {
  const fixture = fixtureEvidence({
    telemetry: {
      overall_status: "passed",
      diagnostic_context: "secret-token-should-not-copy",
    },
    manual: {
      approval_note: "contains-token-value",
    },
  });
  const result = run(readinessArgs(fixture), {
    env: {
      ...process.env,
      PILOT_APPROVAL_NOTE: "Secret note should not be copied into the report.",
    },
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  const reportText = readFileSync(fixture.out, "utf8");
  assert.doesNotMatch(reportText, /secret-token-should-not-copy/);
  assert.doesNotMatch(reportText, /contains-token-value/);
  assert.doesNotMatch(reportText, /Secret note/);
});

test("production-pilot workflow requires B4 evidence and manual readiness before Azure login", () => {
  const workflow = readFileSync(join(root, ".github/workflows/azure-promote-pilot.yml"), "utf8");
  assert.match(workflow, /Download staging validation evidence/);
  assert.match(workflow, /name: azure-staging-validation/);
  assert.match(workflow, /manual_accessibility_review_passed:[\s\S]*?default: "false"/);
  assert.match(workflow, /manual_security_review_passed:[\s\S]*?default: "false"/);
  assert.match(workflow, /Validate production-pilot readiness gate/);
  assert.match(workflow, /npm run azure:pilot:readiness/);
  assert.ok(workflow.indexOf("Validate production-pilot readiness gate") < workflow.indexOf("Azure login"));
  assert.match(workflow, /environment: production-pilot/);
  assert.doesNotMatch(workflow, /pull_request_target/);
});
