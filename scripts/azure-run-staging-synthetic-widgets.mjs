#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { join } from "node:path";
import { assertEnvironment, parseArgs, repoRoot, utcTimestamp, writeJson } from "./azure-release-lib.mjs";

const args = parseArgs(process.argv.slice(2));
const environment = String(args.environment ?? args._[0] ?? "staging");
assertEnvironment(environment);
if (environment !== "staging") throw new Error("Synthetic widget bootstrap wrapper only supports staging.");
if (process.env.APP_ENV !== "staging") throw new Error("APP_ENV=staging is required.");
if (process.env.WIDGET_STAGING_SYNTHETIC_BOOTSTRAP !== "1") throw new Error("WIDGET_STAGING_SYNTHETIC_BOOTSTRAP=1 is required.");

const execute = Boolean(args.execute || args._.includes("execute"));
const namePrefix = String(args["name-prefix"] ?? process.env.AZURE_NAME_PREFIX ?? "yoranix");
const location = String(args.location ?? process.env.AZURE_LOCATION ?? "australiaeast");
const resourceGroup = String(args["resource-group"] ?? process.env.AZURE_RESOURCE_GROUP ?? `${namePrefix}-staging-rg`);
const managedEnvironmentName = String(args["managed-environment"] ?? process.env.AZURE_CONTAINER_APPS_ENVIRONMENT ?? `${namePrefix}-staging-cae`);
const keyVaultName = String(args["key-vault"] ?? process.env.AZURE_KEY_VAULT_NAME ?? `${namePrefix}stagingkv`);
const jobName = String(args.job ?? process.env.AZURE_SYNTHETIC_WIDGET_BOOTSTRAP_JOB ?? `${namePrefix}-staging-synth-widget-job`);
const image = String(args.image ?? process.env.API_IMAGE_REF ?? process.env.AZURE_API_IMAGE ?? "");
const acrLoginServer = String(args["acr-login-server"] ?? process.env.AZURE_ACR_LOGIN_SERVER ?? image.split("/")[0] ?? "");
const migrationIdentityId = String(args["migration-identity-id"] ?? process.env.AZURE_MIGRATION_IDENTITY_ID ?? "");
const cdnHostName = String(args["cdn-host-name"] ?? process.env.STAGING_CDN_HOST_NAME ?? "cdn.staging.example.invalid");

const report = {
  schema_version: "1.0",
  environment,
  timestamp: utcTimestamp(),
  mode: execute ? "execute" : "dry_run",
  resource_group: resourceGroup,
  managed_environment: managedEnvironmentName,
  job: jobName,
  status: "planned",
};

function requireValue(value, label) {
  if (!value) throw new Error(`${label} is required to create the synthetic widget bootstrap job.`);
}

function runAz(commandArgs, message) {
  const result = spawnSync("az", commandArgs, { stdio: "inherit", shell: process.platform === "win32" });
  if (result.status !== 0) throw new Error(message);
}

if (execute) {
  requireValue(image, "API image digest/reference");
  requireValue(acrLoginServer, "ACR login server");
  requireValue(migrationIdentityId, "Migration managed identity id");

  runAz([
    "deployment", "group", "create",
    "--resource-group", resourceGroup,
    "--name", `${namePrefix}-${environment}-synthetic-widget-job-${Date.now()}`,
    "--template-file", "infrastructure/azure/modules/synthetic-widget-job.bicep",
    "--parameters",
    `location=${location}`,
    `namePrefix=${namePrefix}`,
    `environmentName=${environment}`,
    `managedEnvironmentName=${managedEnvironmentName}`,
    `acrLoginServer=${acrLoginServer}`,
    `keyVaultName=${keyVaultName}`,
    `syntheticWidgetBootstrapImage=${image}`,
    `syntheticWidgetBootstrapIdentityId=${migrationIdentityId}`,
    `cdnHostName=${cdnHostName}`,
    `tags=${JSON.stringify({ environment, service: "chatbotweb", managed_by: "bicep", component: "synthetic-widget-bootstrap" })}`,
  ], "Failed to create or update staging synthetic widget bootstrap job resource.");

  const envVars = ["APP_ENV=staging", "WIDGET_STAGING_SYNTHETIC_BOOTSTRAP=1"];
  if (process.env.STAGING_API_URL) envVars.push(`STAGING_API_URL=${process.env.STAGING_API_URL}`);
  runAz([
    "containerapp", "job", "update",
    "--name", jobName,
    "--resource-group", resourceGroup,
    "--image", image,
    "--command", "python",
    "--args", "-m", "app.operations.staging_synthetic_widgets",
    "--set-env-vars", ...envVars,
  ], "Failed to update staging synthetic widget bootstrap job. Ensure the job uses managed Key Vault configuration.");
  runAz(["containerapp", "job", "start", "--name", jobName, "--resource-group", resourceGroup], "Failed to start staging synthetic widget bootstrap job.");
  report.status = "started";
} else {
  report.status = "dry_run_ready";
}

writeJson(join(repoRoot, "artifacts/azure-staging-validation", "synthetic-widgets-bootstrap-job.json"), report);
console.log(JSON.stringify(report, null, 2));
