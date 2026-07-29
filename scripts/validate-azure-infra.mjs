#!/usr/bin/env node
import { existsSync, readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const requiredFiles = [
  "infrastructure/azure/main.bicep",
  "infrastructure/azure/modules/container-apps.bicep",
  "infrastructure/azure/modules/application-container-apps.bicep",
  "infrastructure/azure/modules/migration-job.bicep",
  "infrastructure/azure/modules/synthetic-widget-job.bicep",
  "infrastructure/azure/modules/workload-role-assignments.bicep",
  "infrastructure/azure/modules/container-registry.bicep",
  "infrastructure/azure/modules/front-door.bicep",
  "infrastructure/azure/modules/key-vault.bicep",
  "infrastructure/azure/modules/monitoring.bicep",
  "infrastructure/azure/modules/postgres.bicep",
  "infrastructure/azure/modules/redis.bicep",
  "infrastructure/azure/modules/storage.bicep",
  "infrastructure/azure/environments/staging.bicepparam",
  "infrastructure/azure/environments/pilot.bicepparam",
  "apps/api/Dockerfile",
  "apps/web/Dockerfile",
];

const failures = [];
const warnings = [];

function read(relativePath) {
  const fullPath = path.join(root, relativePath);
  if (!existsSync(fullPath)) {
    failures.push(`Missing required file: ${relativePath}`);
    return "";
  }
  return readFileSync(fullPath, "utf8");
}

function requireContains(name, content, needle) {
  if (!content.includes(needle)) {
    failures.push(`${name} must contain ${needle}`);
  }
}

function requireNotContains(name, content, needle) {
  if (content.includes(needle)) {
    failures.push(`${name} must not contain ${needle}`);
  }
}

for (const file of requiredFiles) {
  read(file);
}

const main = read("infrastructure/azure/main.bicep");
const acr = read("infrastructure/azure/modules/container-registry.bicep");
const apps = read("infrastructure/azure/modules/container-apps.bicep");
const appWorkloads = read("infrastructure/azure/modules/application-container-apps.bicep");
const migrationJob = read("infrastructure/azure/modules/migration-job.bicep");
const syntheticWidgetJob = read("infrastructure/azure/modules/synthetic-widget-job.bicep");
const workloadRoleAssignments = read("infrastructure/azure/modules/workload-role-assignments.bicep");
const postgres = read("infrastructure/azure/modules/postgres.bicep");
const storage = read("infrastructure/azure/modules/storage.bicep");
const keyVault = read("infrastructure/azure/modules/key-vault.bicep");
const frontDoor = read("infrastructure/azure/modules/front-door.bicep");
const stagingParams = read("infrastructure/azure/environments/staging.bicepparam");
const pilotParams = read("infrastructure/azure/environments/pilot.bicepparam");
const apiDockerfile = read("apps/api/Dockerfile");
const webDockerfile = read("apps/web/Dockerfile");

requireContains("main.bicep", main, "targetScope = 'subscription'");
requireContains("main.bicep", main, "Microsoft.Resources/resourceGroups");
requireContains("main.bicep", main, "modules/postgres.bicep");
requireContains("main.bicep", main, "modules/front-door.bicep");
requireContains("main.bicep", main, "modules/workload-role-assignments.bicep");
requireContains("main.bicep", main, "scope: resourceGroup(resourceGroupName)");
requireContains("main.bicep", main, "@secure()");

requireContains("container-registry.bicep", acr, "adminUserEnabled: false");
requireContains("container-registry.bicep", acr, "anonymousPullEnabled: false");
requireNotContains("container-registry.bicep", acr, "adminUserEnabled: true");

requireContains("postgres.bicep", postgres, "Microsoft.DBforPostgreSQL/flexibleServers");
requireContains("postgres.bicep", postgres, "publicNetworkAccess: 'Disabled'");
requireContains("postgres.bicep", postgres, "require_secure_transport");
requireNotContains("postgres.bicep", postgres, "publicNetworkAccess: 'Enabled'");

requireContains("storage.bicep", storage, "allowBlobPublicAccess: false");
requireContains("storage.bicep", storage, "supportsHttpsTrafficOnly: true");
requireContains("storage.bicep", storage, "name: '$web'");
requireContains("storage.bicep", storage, "primaryEndpoints.blob");
requireContains("storage.bicep", storage, "widgetStaticOriginPath");
requireNotContains("storage.bicep", storage, "staticWebsite");
requireNotContains("storage.bicep", storage, "allowSharedKeyAccess: true");

requireContains("key-vault.bicep", keyVault, "enableRbacAuthorization: true");
requireContains("key-vault.bicep", keyVault, "enableSoftDelete: true");

requireContains("container-apps.bicep", apps, "Microsoft.App/managedEnvironments");
requireContains("container-apps.bicep", apps, "Microsoft.ManagedIdentity/userAssignedIdentities");
requireContains("application-container-apps.bicep", appWorkloads, "/health/live");
requireContains("application-container-apps.bicep", appWorkloads, "/health/ready");
requireContains("application-container-apps.bicep", appWorkloads, "keyVaultUrl");
requireContains("application-container-apps.bicep", appWorkloads, "UserAssigned");
requireContains("application-container-apps.bicep", appWorkloads, "param enableRedis bool");
requireContains("application-container-apps.bicep", appWorkloads, "redisSecrets = enableRedis ?");
requireContains("application-container-apps.bicep", appWorkloads, "redisEnvironment = enableRedis ?");
requireContains("application-container-apps.bicep", appWorkloads, "rateLimitLocalFallbackEnabled = enableRedis ? 'false' : (environmentName == 'staging' ? 'true' : 'false')");
const apiSecretBlock = appWorkloads.slice(appWorkloads.indexOf("secrets: concat(["), appWorkloads.indexOf("], redisSecrets)"));
if (apiSecretBlock.includes("api-redis-url") || apiSecretBlock.includes("redis-url")) {
  failures.push("application-container-apps.bicep must not include Redis secrets in the base API secret list when staging has Redis disabled.");
}
const apiEnvBlock = appWorkloads.slice(appWorkloads.indexOf("env: concat(["), appWorkloads.indexOf("], redisEnvironment)"));
if (apiEnvBlock.includes("REDIS_URL")) {
  failures.push("application-container-apps.bicep must not include REDIS_URL in the base API environment list when staging has Redis disabled.");
}
requireContains("staging.bicepparam", stagingParams, "param enableRedis = false");
requireContains("azure-deploy-apps.mjs", read("scripts/azure-deploy-apps.mjs"), "environment === \"staging\" ? \"false\" : \"true\"");
requireContains("azure-deploy-apps.mjs", read("scripts/azure-deploy-apps.mjs"), "`enableRedis=${enableRedis}`");
requireContains("migration-job.bicep", migrationJob, "Microsoft.App/jobs");
requireContains("synthetic-widget-job.bicep", syntheticWidgetJob, "Microsoft.App/jobs");
requireContains("synthetic-widget-job.bicep", syntheticWidgetJob, "triggerType: 'Manual'");
requireContains("synthetic-widget-job.bicep", syntheticWidgetJob, "python");
requireContains("synthetic-widget-job.bicep", syntheticWidgetJob, "app.operations.staging_synthetic_widgets");
requireContains("synthetic-widget-job.bicep", syntheticWidgetJob, "APP_ENV");
requireContains("synthetic-widget-job.bicep", syntheticWidgetJob, "WIDGET_STAGING_SYNTHETIC_BOOTSTRAP");
requireContains("synthetic-widget-job.bicep", syntheticWidgetJob, "api-database-url");
requireContains("synthetic-widget-job.bicep", syntheticWidgetJob, "keyVaultUrl");
requireContains("synthetic-widget-job.bicep", syntheticWidgetJob, "identity: syntheticWidgetBootstrapIdentityId");
requireContains("synthetic-widget-job.bicep", syntheticWidgetJob, "registries");
requireNotContains("synthetic-widget-job.bicep", syntheticWidgetJob, "adminUserEnabled");
requireNotContains("synthetic-widget-job.bicep", syntheticWidgetJob, "password");
requireNotContains("synthetic-widget-job.bicep", syntheticWidgetJob, "DATABASE_URL', value");
requireContains("application-container-apps.bicep", appWorkloads, "module syntheticWidgetBootstrapJob 'synthetic-widget-job.bicep'");
requireContains("application-container-apps.bicep", appWorkloads, "enableSyntheticWidgetBootstrapJob && environmentName == 'staging'");
requireContains("application-container-apps.bicep", appWorkloads, "syntheticWidgetBootstrapImage: apiImage");
requireContains("application-container-apps.bicep", appWorkloads, "syntheticWidgetBootstrapIdentityId: migrationIdentityId");
requireContains("staging.bicepparam", stagingParams, "param enableSyntheticWidgetBootstrapJob = true");
requireContains("pilot.bicepparam", pilotParams, "param enableSyntheticWidgetBootstrapJob = false");
requireContains("azure-deploy-apps.mjs", read("scripts/azure-deploy-apps.mjs"), "environment === \"staging\" ? \"true\" : \"false\"");
requireContains("azure-run-staging-synthetic-widgets.mjs", read("scripts/azure-run-staging-synthetic-widgets.mjs"), "synthetic-widget-job.bicep");
requireContains("azure-run-staging-synthetic-widgets.mjs", read("scripts/azure-run-staging-synthetic-widgets.mjs"), "APP_ENV=staging");
requireContains("azure-run-staging-synthetic-widgets.mjs", read("scripts/azure-run-staging-synthetic-widgets.mjs"), "WIDGET_STAGING_SYNTHETIC_BOOTSTRAP=1");
requireContains("workload-role-assignments.bicep", workloadRoleAssignments, "AcrPull");
requireContains("workload-role-assignments.bicep", workloadRoleAssignments, "KeyVaultSecretsUser");
requireContains("workload-role-assignments.bicep", workloadRoleAssignments, "StorageBlobDataContributor");
requireNotContains("container-apps.bicep", apps, "--reload");
requireNotContains("container-apps.bicep", apps, "npm run dev");
requireNotContains("application-container-apps.bicep", appWorkloads, "--reload");
requireNotContains("application-container-apps.bicep", appWorkloads, "npm run dev");

requireContains("front-door.bicep", frontDoor, "Standard_AzureFrontDoor");
requireContains("front-door.bicep", frontDoor, "HttpsOnly");
requireContains("front-door.bicep", frontDoor, "originPath: widgetStaticOriginPath");
const widgetOriginStart = frontDoor.indexOf("resource widgetStaticOrigin");
const staticRouteStart = frontDoor.indexOf("resource staticRoute");
const originPathPosition = frontDoor.indexOf("originPath: widgetStaticOriginPath");
if (widgetOriginStart >= 0 && staticRouteStart > widgetOriginStart) {
  const widgetOriginBlock = frontDoor.slice(widgetOriginStart, staticRouteStart);
  if (widgetOriginBlock.includes("originPath")) {
    failures.push("front-door.bicep must not put originPath on the widget static origin resource.");
  }
}
if (staticRouteStart < 0 || originPathPosition < staticRouteStart) {
  failures.push("front-door.bicep must put widgetStaticOriginPath on the static route resource.");
}
requireContains("front-door.bicep", frontDoor, "immutable");
requireContains("front-door.bicep", frontDoor, "no-cache, must-revalidate");
requireNotContains("front-door.bicep", frontDoor, "AllowInsecure");

for (const [name, content] of [["staging.bicepparam", stagingParams], ["pilot.bicepparam", pilotParams]]) {
  requireNotContains(name, content, "postgresAdministratorPassword");
  requireNotContains(name, content, "DATABASE_URL");
  requireNotContains(name, content, "redis://");
  requireNotContains(name, content, "http://");
  requireNotContains(name, content, "localhost");
}
requireContains("pilot.bicepparam", pilotParams, "<approved-domain-required>");
const azureWorkflows = [
  ["azure-validate.yml", read(".github/workflows/azure-validate.yml")],
  ["azure-deploy-staging.yml", read(".github/workflows/azure-deploy-staging.yml")],
  ["azure-promote-pilot.yml", read(".github/workflows/azure-promote-pilot.yml")],
  ["azure-rollback.yml", read(".github/workflows/azure-rollback.yml")],
];
for (const [name, content] of azureWorkflows) {
  requireNotContains(name, content, "pull_request_target");
  requireNotContains(name, content, ":latest");
}
for (const [name, content] of azureWorkflows.filter(([name]) => name !== "azure-validate.yml")) {
  requireContains(name, content, "id-token: write");
  requireContains(name, content, "concurrency:");
  requireContains(name, content, "azure/login@v2");
}
requireContains("azure-promote-pilot.yml", read(".github/workflows/azure-promote-pilot.yml"), "environment: production-pilot");
requireContains("azure-promote-pilot.yml", read(".github/workflows/azure-promote-pilot.yml"), "Download staged release artifact");
requireContains("azure-rollback.yml", read(".github/workflows/azure-rollback.yml"), "execute");

requireNotContains("apps/api/Dockerfile", apiDockerfile, "--reload");
requireContains("apps/api/Dockerfile", apiDockerfile, "uvicorn");
requireContains("apps/api/Dockerfile", apiDockerfile, "USER appuser");
requireNotContains("apps/web/Dockerfile", webDockerfile, "npm run dev");
requireContains("apps/web/Dockerfile", webDockerfile, "npm run build");
requireContains("apps/web/Dockerfile", webDockerfile, "USER nextjs");

const sensitiveOutputPattern = /^\s*output\s+\w*(secret|password|connectionstring|sharedkey)\w*\s+string\b/iu;
for (const file of requiredFiles.filter((file) => file.endsWith(".bicep"))) {
  const lines = read(file).split(/\r?\n/);
  for (let index = 0; index < lines.length; index += 1) {
    if (sensitiveOutputPattern.test(lines[index]) && !/^\s*@secure\(\)\s*$/.test(lines[index - 1] ?? "")) {
      failures.push(`${file} appears to output a sensitive value without @secure(): ${lines[index].trim()}`);
    }
  }
}

const azVersion = spawnSync("az", ["bicep", "version"], { encoding: "utf8", shell: process.platform === "win32" });
if (azVersion.status === 0) {
  const build = spawnSync("az", ["bicep", "build", "--file", "infrastructure/azure/main.bicep"], {
    encoding: "utf8",
    shell: process.platform === "win32",
  });
  if (build.status !== 0) {
    failures.push(`az bicep build failed:\n${build.stdout}\n${build.stderr}`);
  }
} else {
  warnings.push("Azure CLI/Bicep not available; skipped az bicep build. Static IaC checks still ran.");
}

if (failures.length > 0) {
  console.error("Azure infrastructure validation failed:");
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  process.exit(1);
}

console.log("Azure infrastructure validation passed.");
for (const warning of warnings) {
  console.warn(`Warning: ${warning}`);
}
