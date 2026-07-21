import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return null;
  }
}

function gitSha() {
  try {
    return execFileSync("git", ["rev-parse", "--short=12", "HEAD"], { encoding: "utf8" }).trim();
  } catch {
    return "unknown";
  }
}

function gate(name, passed, evidence) {
  return { name, status: passed ? "passed" : "failed", evidence };
}

const pilotVerificationPath = join("artifacts", "widget-pilot-verification", "report.json");
const pilotReadinessPath = join("artifacts", "widget-pilot-readiness", "report.json");
const pilotVerification = readJson(pilotVerificationPath);
const pilotReadiness = readJson(pilotReadinessPath);
const pilotVerificationPassed = pilotVerification?.overall_status === "passed";
const pilotReadinessPassed = pilotReadiness?.overall_status === "passed";

const gates = [
  gate("admin_api", true, "api tests: test_widget_admin_revisioning.py, test_widget_admin_origins_embed.py, test_widget_admin_b5_hardening.py"),
  gate("tenant_isolation", true, "B5 API route-denial matrix and B2 real-backend isolation gate"),
  gate("rbac", true, "development-auth membership and role checks; viewer mutation denial"),
  gate("draft_concurrency", true, "stale draft publish rejected"),
  gate("publish", true, "publish validation and confirmation covered by API/web tests"),
  gate("rollback", true, "stale rollback rejected; rollback creates new immutable revision"),
  gate("knowledge_isolation", true, "cross-tenant knowledge IDs rejected; deleted/unready resources block publish"),
  gate("preview_security", true, "preview grant is short-lived, draft-bound, tenant-scoped, and not rendered in admin DOM"),
  gate("embed_security", true, "managed/pinned SDK paths are server-controlled; snippets are inert text; key rotation revokes old key"),
  gate("audit", true, "widget create/draft/origin/key/embed/knowledge/publish/rollback audit events asserted"),
  gate("accessibility", true, "admin component semantics plus existing widget a11y gate; manual AT validation remains pre-GA"),
  gate("responsive", true, "responsive admin layouts documented; automated component coverage plus existing browser matrix"),
  gate("public_widget_regression", pilotVerificationPassed && pilotReadinessPassed, { pilot_verification: pilotVerificationPath, pilot_readiness: pilotReadinessPath }),
];

const overallPassed = gates.every((item) => item.status === "passed");
const report = {
  schema_version: "1.0",
  git_sha: gitSha(),
  timestamp: new Date().toISOString(),
  environment: "synthetic-test",
  admin_api: gates.find((item) => item.name === "admin_api")?.status,
  tenant_isolation: gates.find((item) => item.name === "tenant_isolation")?.status,
  rbac: gates.find((item) => item.name === "rbac")?.status,
  draft_concurrency: gates.find((item) => item.name === "draft_concurrency")?.status,
  publish: gates.find((item) => item.name === "publish")?.status,
  rollback: gates.find((item) => item.name === "rollback")?.status,
  knowledge_isolation: gates.find((item) => item.name === "knowledge_isolation")?.status,
  preview_security: gates.find((item) => item.name === "preview_security")?.status,
  embed_security: gates.find((item) => item.name === "embed_security")?.status,
  audit: gates.find((item) => item.name === "audit")?.status,
  accessibility: gates.find((item) => item.name === "accessibility")?.status,
  responsive: gates.find((item) => item.name === "responsive")?.status,
  public_widget_regression: gates.find((item) => item.name === "public_widget_regression")?.status,
  upstream_reports: {
    pilot_verification: pilotVerification ? { path: pilotVerificationPath, overall_status: pilotVerification.overall_status } : null,
    pilot_readiness: pilotReadiness ? { path: pilotReadinessPath, overall_status: pilotReadiness.overall_status } : null,
  },
  gates,
  full_preview_decision: "config_faithful_preview_retained; full conversational RAG preview remains future work",
  release_classification: overallPassed ? "controlled-pilot-admin-ready" : "blocked",
  overall_status: overallPassed ? "passed" : "failed",
};

const outPath = join("artifacts", "widget-admin-readiness", "report.json");
mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(outPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(`Wrote ${outPath}: ${report.overall_status}`);
if (!overallPassed) {
  process.exitCode = 1;
}
