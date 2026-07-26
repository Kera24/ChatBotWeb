import assert from "node:assert/strict";
import { existsSync, readFileSync, rmSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";

const root = process.cwd();
const evidenceRoot = join(root, "artifacts/azure-staging-validation");

function run(args, options = {}) {
  return spawnSync(process.execPath, args, {
    cwd: root,
    encoding: "utf8",
    env: {
      ...process.env,
      AZURE_SUBSCRIPTION_ID: "",
      AZURE_POSTGRES_ADMIN_PASSWORD: "",
      STAGING_WIDGET_PUBLIC_KEY_ALPHA: "",
      STAGING_WIDGET_PUBLIC_KEY_BETA: "",
    },
    ...options,
  });
}

function readEvidence(name) {
  return JSON.parse(readFileSync(join(evidenceRoot, name), "utf8"));
}

test("B4 staging validator rejects non-staging environments", () => {
  for (const environment of ["pilot", "production", "prod", "production-pilot"]) {
    const result = run(["scripts/azure-staging-validate.mjs", "--environment", environment]);
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /only supports direct execution against staging/);
  }
});

test("B4 validation writes blocked evidence without secret values", () => {
  rmSync(evidenceRoot, { recursive: true, force: true });
  const result = run(["scripts/azure-staging-validate.mjs", "--environment", "staging"], {
    env: {
      ...process.env,
      AZURE_SUBSCRIPTION_ID: "",
      AZURE_POSTGRES_ADMIN_PASSWORD: "super-secret-password",
      STAGING_API_URL: "https://example.test/path?preview_grant=leakme",
    },
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  const reportText = readFileSync(join(evidenceRoot, "report.json"), "utf8");
  assert.doesNotMatch(reportText, /super-secret-password/);
  assert.doesNotMatch(reportText, /leakme/);
  const report = JSON.parse(reportText);
  assert.equal(report.overall_status, "blocked_missing_prerequisites");
  assert.equal(report.classification, "staging deployment blocked before execution");
});

test("live validation wrappers record missing prerequisites safely", () => {
  rmSync(evidenceRoot, { recursive: true, force: true });
  const browser = run(["scripts/azure-live-browser-smoke.mjs", "--environment", "staging"]);
  const telemetry = run(["scripts/azure-telemetry-validate.mjs", "--environment", "staging"]);
  const alerts = run(["scripts/azure-alert-validate.mjs", "--environment", "staging"]);
  const rollback = run(["scripts/azure-rollback-drill.mjs", "--environment", "staging"]);
  for (const result of [browser, telemetry, alerts, rollback]) {
    assert.equal(result.status, 0, result.stderr || result.stdout);
  }
  assert.equal(readEvidence("browser-smoke.json").status, "blocked_missing_prerequisites");
  assert.equal(readEvidence("telemetry.json").status, "blocked_missing_prerequisites");
  assert.equal(readEvidence("alerts.json").status, "blocked_missing_prerequisites");
  assert.equal(readEvidence("rollback.json").status, "blocked_missing_prerequisites");
});

test("staging validation workflow is manual, staging-scoped, and never production-pilot", () => {
  const workflowPath = join(root, ".github/workflows/azure-validate-staging.yml");
  assert.ok(existsSync(workflowPath));
  const content = readFileSync(workflowPath, "utf8");
  assert.match(content, /workflow_dispatch:/);
  assert.match(content, /environment: staging/);
  assert.match(content, /id-token: write/);
  assert.doesNotMatch(content, /pull_request/);
  assert.doesNotMatch(content, /environment: production-pilot/);
  assert.doesNotMatch(content, /--environment pilot/);
  assert.doesNotMatch(content, /:latest/);
  assert.match(content, /npm run azure:staging:validate/);
  assert.match(content, /npm run azure:staging:rollback-drill/);
});
