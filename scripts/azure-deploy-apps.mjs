#!/usr/bin/env node
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { assertEnvironment, parseArgs, repoRoot, utcTimestamp, validateImageRef, writeJson } from "./azure-release-lib.mjs";

const args = parseArgs(process.argv.slice(2));
const environment = String(args.environment ?? args._[0] ?? "staging");
assertEnvironment(environment);
const execute = Boolean(args.execute || args._.includes("execute"));
const apiImage = validateImageRef(String(args["api-image"] ?? args._[1] ?? process.env.API_IMAGE_REF ?? ""), "API image");
const webImage = validateImageRef(String(args["web-image"] ?? args._[2] ?? process.env.WEB_IMAGE_REF ?? ""), "Web image");
const namePrefix = String(args["name-prefix"] ?? process.env.AZURE_NAME_PREFIX ?? "yoranix");
const location = String(args.location ?? process.env.AZURE_LOCATION ?? "australiaeast");
const resourceGroup = String(args["resource-group"] ?? process.env.AZURE_RESOURCE_GROUP ?? `${namePrefix}-${environment}-rg`);
const apiApp = String(args["api-app"] ?? process.env.AZURE_API_CONTAINER_APP ?? `${namePrefix}-${environment}-ca-api`);
const webApp = String(args["web-app"] ?? process.env.AZURE_WEB_CONTAINER_APP ?? `${namePrefix}-${environment}-ca-web`);
const managedEnvironmentName = String(args["managed-environment"] ?? process.env.AZURE_CONTAINER_APPS_ENVIRONMENT ?? `${namePrefix}-${environment}-cae`);
const keyVaultName = String(args["key-vault"] ?? process.env.AZURE_KEY_VAULT_NAME ?? `${namePrefix}${environment}kv`);
const acrLoginServer = String(args["acr-login-server"] ?? process.env.AZURE_ACR_LOGIN_SERVER ?? apiImage.split("/")[0] ?? "");
const apiIdentityId = String(args["api-identity-id"] ?? process.env.AZURE_API_IDENTITY_ID ?? "");
const webIdentityId = String(args["web-identity-id"] ?? process.env.AZURE_WEB_IDENTITY_ID ?? "");
const appHostName = String(args["app-host-name"] ?? process.env.STAGING_APP_HOST_NAME ?? "app.staging.example.invalid");
const apiHostName = String(args["api-host-name"] ?? process.env.STAGING_API_HOST_NAME ?? "api.staging.example.invalid");
const widgetApiHostName = String(args["widget-api-host-name"] ?? process.env.STAGING_WIDGET_API_HOST_NAME ?? "widget-api.staging.example.invalid");
const widgetHostName = String(args["widget-host-name"] ?? process.env.STAGING_WIDGET_HOST_NAME ?? "widget.staging.example.invalid");
const cdnHostName = String(args["cdn-host-name"] ?? process.env.STAGING_CDN_HOST_NAME ?? "cdn.staging.example.invalid");
const enableRedis = parseBoolean(args["enable-redis"] ?? process.env.AZURE_ENABLE_REDIS ?? (environment === "staging" ? "false" : "true"));

const report = {
  schema_version: "1.0",
  environment,
  timestamp: utcTimestamp(),
  mode: execute ? "execute" : "dry_run",
  resource_group: resourceGroup,
  api_app: apiApp,
  web_app: webApp,
  managed_environment: managedEnvironmentName,
  api_image: apiImage,
  web_image: webImage,
  status: "planned",
};

function parseBoolean(value) {
  const normalized = String(value).trim().toLowerCase();
  if (["1", "true", "yes"].includes(normalized)) return true;
  if (["0", "false", "no"].includes(normalized)) return false;
  throw new Error(`Invalid boolean value for enableRedis: ${value}`);
}

function requireValue(value, label) {
  if (!value) throw new Error(`${label} is required for Container App deployment.`);
}

if (execute) {
  requireValue(acrLoginServer, "ACR login server");
  requireValue(apiIdentityId, "API managed identity id");
  requireValue(webIdentityId, "Web managed identity id");

  const result = spawnSync("az", [
    "deployment", "group", "create",
    "--resource-group", resourceGroup,
    "--name", `${namePrefix}-${environment}-container-apps-${Date.now()}`,
    "--template-file", "infrastructure/azure/modules/application-container-apps.bicep",
    "--parameters",
    `location=${location}`,
    `namePrefix=${namePrefix}`,
    `environmentName=${environment}`,
    `managedEnvironmentName=${managedEnvironmentName}`,
    `acrLoginServer=${acrLoginServer}`,
    `keyVaultName=${keyVaultName}`,
    `apiImage=${apiImage}`,
    `webImage=${webImage}`,
    `apiIdentityId=${apiIdentityId}`,
    `webIdentityId=${webIdentityId}`,
    `appHostName=${appHostName}`,
    `apiHostName=${apiHostName}`,
    `widgetApiHostName=${widgetApiHostName}`,
    `widgetHostName=${widgetHostName}`,
    `cdnHostName=${cdnHostName}`,
    `enableRedis=${enableRedis}`,
    `tags=${JSON.stringify({ environment, service: "chatbotweb", managed_by: "bicep" })}`,
  ], { stdio: "inherit", shell: process.platform === "win32" });
  if (result.status !== 0) throw new Error("Failed to create or update Container Apps.");
  report.status = "updated";
} else {
  report.status = "dry_run_ready";
}

writeJson(join(repoRoot, "artifacts/azure-deployment", environment, "container-apps-report.json"), report);
console.log(JSON.stringify(report, null, 2));
