#!/usr/bin/env node
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { assertEnvironment, parseArgs, repoRoot, utcTimestamp, validateImageRef, writeJson } from "./azure-release-lib.mjs";

const args = parseArgs(process.argv.slice(2));
const environment = String(args.environment ?? args._[0] ?? "staging");
assertEnvironment(environment);
const execute = Boolean(args.execute || args._.includes("execute"));
const image = validateImageRef(String(args.image ?? args._[1] ?? process.env.API_IMAGE_REF ?? ""), "migration image");
const namePrefix = String(args["name-prefix"] ?? process.env.AZURE_NAME_PREFIX ?? "yoranix");
const location = String(args.location ?? process.env.AZURE_LOCATION ?? "australiaeast");
const jobName = String(args.job ?? process.env.AZURE_MIGRATION_JOB_NAME ?? `${namePrefix}-${environment}-job-migrate`);
const resourceGroup = String(args["resource-group"] ?? process.env.AZURE_RESOURCE_GROUP ?? `${namePrefix}-${environment}-rg`);
const managedEnvironmentName = String(args["managed-environment"] ?? process.env.AZURE_CONTAINER_APPS_ENVIRONMENT ?? `${namePrefix}-${environment}-cae`);
const keyVaultName = String(args["key-vault"] ?? process.env.AZURE_KEY_VAULT_NAME ?? `${namePrefix}${environment}kv`);
const acrLoginServer = String(args["acr-login-server"] ?? process.env.AZURE_ACR_LOGIN_SERVER ?? image.split("/")[0] ?? "");
const migrationIdentityId = String(args["migration-identity-id"] ?? process.env.AZURE_MIGRATION_IDENTITY_ID ?? "");

const report = {
  schema_version: "1.0",
  environment,
  timestamp: utcTimestamp(),
  mode: execute ? "execute" : "dry_run",
  migration_job: jobName,
  resource_group: resourceGroup,
  managed_environment: managedEnvironmentName,
  image,
  status: "planned",
};

function requireValue(value, label) {
  if (!value) throw new Error(`${label} is required for migration job deployment.`);
}

function run(command, commandArgs, errorMessage) {
  const result = spawnSync(command, commandArgs, { stdio: "inherit", shell: process.platform === "win32" });
  if (result.status !== 0) throw new Error(errorMessage);
}

if (execute) {
  requireValue(acrLoginServer, "ACR login server");
  requireValue(migrationIdentityId, "Migration managed identity id");

  run("az", [
    "deployment", "group", "create",
    "--resource-group", resourceGroup,
    "--name", `${namePrefix}-${environment}-migration-job-${Date.now()}`,
    "--template-file", "infrastructure/azure/modules/migration-job.bicep",
    "--parameters",
    `location=${location}`,
    `namePrefix=${namePrefix}`,
    `environmentName=${environment}`,
    `managedEnvironmentName=${managedEnvironmentName}`,
    `acrLoginServer=${acrLoginServer}`,
    `keyVaultName=${keyVaultName}`,
    `migrationImage=${image}`,
    `migrationIdentityId=${migrationIdentityId}`,
    `tags=${JSON.stringify({ environment, service: "chatbotweb", managed_by: "bicep", component: "migration" })}`,
  ], "Failed to create or update migration job.");

  run("az", [
    "containerapp", "job", "start",
    "--name", jobName,
    "--resource-group", resourceGroup,
  ], "Failed to start migration job.");
  report.status = "started";
} else {
  report.status = "dry_run_ready";
}

writeJson(join(repoRoot, "artifacts/azure-deployment", environment, "migration-report.json"), report);
console.log(JSON.stringify(report, null, 2));
