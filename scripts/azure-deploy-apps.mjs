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
const resourceGroup = String(args["resource-group"] ?? process.env.AZURE_RESOURCE_GROUP ?? `yoranix-${environment}-rg`);
const apiApp = String(args["api-app"] ?? process.env.AZURE_API_CONTAINER_APP ?? `yoranix-${environment}-ca-api`);
const webApp = String(args["web-app"] ?? process.env.AZURE_WEB_CONTAINER_APP ?? `yoranix-${environment}-ca-web`);

const report = {
  schema_version: "1.0",
  environment,
  timestamp: utcTimestamp(),
  mode: execute ? "execute" : "dry_run",
  resource_group: resourceGroup,
  api_app: apiApp,
  web_app: webApp,
  api_image: apiImage,
  web_image: webImage,
  status: "planned",
};

function runUpdate(appName, image) {
  const result = spawnSync("az", [
    "containerapp", "update",
    "--name", appName,
    "--resource-group", resourceGroup,
    "--image", image,
  ], { stdio: "inherit", shell: process.platform === "win32" });
  if (result.status !== 0) throw new Error(`Failed to update Container App ${appName}.`);
}

if (execute) {
  runUpdate(apiApp, apiImage);
  runUpdate(webApp, webImage);
  report.status = "updated";
} else {
  report.status = "dry_run_ready";
}

writeJson(join(repoRoot, "artifacts/azure-deployment", environment, "container-apps-report.json"), report);
console.log(JSON.stringify(report, null, 2));




