import assert from "node:assert/strict";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join, delimiter } from "node:path";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import test from "node:test";

const root = process.cwd();
const evidenceRoot = join(root, "artifacts/azure-staging-validation");
const environmentDir = join(root, "infrastructure/azure/environments");

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

test("staging what-if uses a temporary bicepparam file and never shell-expanded password arguments", () => {
  rmSync(evidenceRoot, { recursive: true, force: true });
  const fake = createFakeAz("success");
  const secret = "postgres-password-never-log";
  const result = run(["scripts/azure-staging-validate.mjs", "--environment", "staging", "--execute"], {
    env: fakeEnv(fake.binDir, {
      AZURE_SUBSCRIPTION_ID: "sub-staging",
      AZURE_TENANT_ID: "tenant-staging",
      AZURE_POSTGRES_ADMIN_PASSWORD: secret,
      AZURE_LOCATION: "australiaeast",
    }),
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);

  const calls = readFakeAzCalls(fake.callsPath);
  const whatIf = calls.find((call) => call.args.slice(0, 3).join(" ") === "deployment sub what-if");
  assert.ok(whatIf, "expected az deployment sub what-if to be invoked");
  assert.ok(whatIf.args.includes("--parameters"));
  assert.ok(!whatIf.args.includes("--template-file"));
  assert.ok(whatIf.args.every((arg) => !arg.includes("$AZURE_POSTGRES_ADMIN_PASSWORD")));
  assert.ok(whatIf.args.every((arg) => !arg.includes(secret)));
  assert.ok(whatIf.parameterFile.endsWith(".generated.bicepparam"));
  assert.equal(whatIf.parameterContent.includes("using '../main.bicep'"), true);
  assert.equal(whatIf.parameterContent.includes("readEnvironmentVariable('AZURE_POSTGRES_ADMIN_PASSWORD')"), true);
  assert.equal(existsSync(whatIf.parameterFile), false, "temporary bicepparam should be deleted after what-if");
  assert.equal(findGeneratedParameterFiles().length, 0);

  const infrastructureText = readFileSync(join(evidenceRoot, "infrastructure.json"), "utf8");
  assert.doesNotMatch(infrastructureText, new RegExp(secret));
  assert.doesNotMatch(infrastructureText, /\$AZURE_POSTGRES_ADMIN_PASSWORD/);
  const infrastructure = JSON.parse(infrastructureText);
  assert.equal(infrastructure.what_if.status, "completed");
  assert.ok(infrastructure.what_if.summary.create_count > 0);
});

test("staging what-if captures final Bicep error context instead of only first warning", () => {
  rmSync(evidenceRoot, { recursive: true, force: true });
  const fake = createFakeAz("bcp-error");
  const secret = "do-not-print-this-password";
  const result = run(["scripts/azure-staging-validate.mjs", "--environment", "staging", "--execute"], {
    env: fakeEnv(fake.binDir, {
      AZURE_SUBSCRIPTION_ID: "sub-staging",
      AZURE_TENANT_ID: "tenant-staging",
      AZURE_POSTGRES_ADMIN_PASSWORD: secret,
    }),
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  const infrastructureText = readFileSync(join(evidenceRoot, "infrastructure.json"), "utf8");
  assert.doesNotMatch(infrastructureText, new RegExp(secret));
  const infrastructure = JSON.parse(infrastructureText);
  assert.equal(infrastructure.what_if.status, "failed");
  assert.match(infrastructure.what_if.error, /BCP035/);
  assert.ok(infrastructure.what_if.error_context.some((line) => /BCP035/.test(line)));
  assert.ok(!/^WARNING/.test(infrastructure.what_if.error));
  assert.equal(findGeneratedParameterFiles().length, 0);
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

function createFakeAz(mode) {
  const dir = join(tmpdir(), `fake-az-${process.pid}-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  const binDir = join(dir, "bin");
  mkdirSync(binDir, { recursive: true });
  const callsPath = join(dir, "calls.jsonl");
  const scriptPath = join(binDir, process.platform === "win32" ? "az.cmd" : "az");
  const nodeScript = join(dir, "fake-az.mjs");
  writeFileSync(
    nodeScript,
    `import { appendFileSync, readFileSync } from "node:fs";\n` +
      `const callsPath = ${JSON.stringify(callsPath)};\n` +
      `const mode = ${JSON.stringify(mode)};\n` +
      `const args = process.argv.slice(2);\n` +
      `let parameterFile = null;\n` +
      `let parameterContent = null;\n` +
      `for (let i = 0; i < args.length; i += 1) {\n` +
      `  if (args[i] === "--parameters") parameterFile = args[i + 1];\n` +
      `}\n` +
      `if (parameterFile && parameterFile.endsWith(".bicepparam")) parameterContent = readFileSync(parameterFile, "utf8");\n` +
      `appendFileSync(callsPath, JSON.stringify({ args, parameterFile, parameterContent }) + "\\n");\n` +
      `if (args[0] === "--version") { console.log("azure-cli 2.99.0"); process.exit(0); }\n` +
      `if (args[0] === "bicep" && args[1] === "version") { console.log("Bicep CLI version 0.99.0"); process.exit(0); }\n` +
      `if (args[0] === "account" && args[1] === "show") { console.log(JSON.stringify({ id: process.env.AZURE_SUBSCRIPTION_ID, tenantId: process.env.AZURE_TENANT_ID || "tenant", name: "staging" })); process.exit(0); }\n` +
      `if (args.slice(0, 3).join(" ") === "deployment sub what-if") {\n` +
      `  if (mode === "success") { console.log("Resource changes: Create api\\nCreate web\\nModify logs"); process.exit(0); }\n` +
      `  console.error("WARNING: Optional provider metadata was not available.");\n` +
      `  console.error("WARNING: Another warning that should not hide the error.");\n` +
      `  console.error("/tmp/main.bicep(40,7) : Error BCP035: The specified parameter postgresAdministratorPassword is required.");\n` +
      `  process.exit(1);\n` +
      `}\n` +
      `console.error("unexpected az args " + args.join(" "));\n` +
      `process.exit(2);\n`,
    "utf8",
  );
  if (process.platform === "win32") {
    writeFileSync(scriptPath, `@echo off\n"${process.execPath}" "${nodeScript}" %*\n`, "utf8");
  } else {
    writeFileSync(scriptPath, `#!/bin/sh\nexec "${process.execPath}" "${nodeScript}" "$@"\n`, { mode: 0o755 });
  }
  return { binDir, callsPath };
}

function fakeEnv(binDir, values) {
  return {
    ...process.env,
    ...values,
    PATH: `${binDir}${delimiter}${process.env.PATH}`,
  };
}

function readFakeAzCalls(callsPath) {
  return readFileSync(callsPath, "utf8")
    .trim()
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

function findGeneratedParameterFiles() {
  return spawnSync(process.execPath, ["-e", `const { readdirSync } = require('node:fs'); const { join } = require('node:path'); const dir = ${JSON.stringify(environmentDir)}; console.log(JSON.stringify(readdirSync(dir).filter((name) => name.endsWith('.generated.bicepparam')).map((name) => join(dir, name))));`], {
    cwd: root,
    encoding: "utf8",
  }).stdout.trim()
    ? JSON.parse(spawnSync(process.execPath, ["-e", `const { readdirSync } = require('node:fs'); const { join } = require('node:path'); const dir = ${JSON.stringify(environmentDir)}; console.log(JSON.stringify(readdirSync(dir).filter((name) => name.endsWith('.generated.bicepparam')).map((name) => join(dir, name))));`], { cwd: root, encoding: "utf8" }).stdout)
    : [];
}
test("synthetic widget bootstrap job is staging-only and securely provisioned", () => {
  const job = readFileSync(join(root, "infrastructure/azure/modules/synthetic-widget-job.bicep"), "utf8");
  const workloads = readFileSync(join(root, "infrastructure/azure/modules/application-container-apps.bicep"), "utf8");
  const staging = readFileSync(join(root, "infrastructure/azure/environments/staging.bicepparam"), "utf8");
  const pilot = readFileSync(join(root, "infrastructure/azure/environments/pilot.bicepparam"), "utf8");
  const wrapper = readFileSync(join(root, "scripts/azure-run-staging-synthetic-widgets.mjs"), "utf8");

  assert.match(job, /resource syntheticWidgetBootstrapJob 'Microsoft\.App\/jobs@/);
  assert.match(job, /triggerType: 'Manual'/);
  assert.match(job, /command: \[ 'python' \]/);
  assert.match(job, /args: \[ '-m', 'app\.operations\.staging_synthetic_widgets' \]/);
  assert.match(job, /APP_ENV/);
  assert.match(job, /WIDGET_STAGING_SYNTHETIC_BOOTSTRAP/);
  assert.match(job, /keyVaultUrl: '\$\{keyVaultUri\}\/secrets\/api-database-url'/);
  assert.match(job, /identity: syntheticWidgetBootstrapIdentityId/);
  assert.match(job, /server: acrLoginServer/);
  assert.doesNotMatch(job, /adminUserEnabled|registryPassword|DATABASE_URL', value|connectionString/i);
  assert.match(workloads, /enableSyntheticWidgetBootstrapJob && environmentName == 'staging'/);
  assert.match(workloads, /syntheticWidgetBootstrapImage: apiImage/);
  assert.match(workloads, /syntheticWidgetBootstrapIdentityId: migrationIdentityId/);
  assert.match(staging, /param enableSyntheticWidgetBootstrapJob = true/);
  assert.match(pilot, /param enableSyntheticWidgetBootstrapJob = false/);
  assert.match(wrapper, /environment !== "staging"/);
  assert.match(wrapper, /APP_ENV=staging/);
  assert.match(wrapper, /WIDGET_STAGING_SYNTHETIC_BOOTSTRAP=1/);
});
