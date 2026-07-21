#!/usr/bin/env node
import { join } from "node:path";
import { assertEnvironment, parseArgs, repoRoot, utcTimestamp, writeJson } from "./azure-release-lib.mjs";

const args = parseArgs(process.argv.slice(2));
const environment = String(args.environment ?? args._[0] ?? "staging");
assertEnvironment(environment);
const baseUrl = String(args["base-url"] ?? process.env.AZURE_DEPLOYED_BASE_URL ?? "");
const apiUrl = String(args["api-url"] ?? process.env.AZURE_DEPLOYED_API_URL ?? "");
const widgetUrl = String(args["widget-url"] ?? process.env.AZURE_DEPLOYED_WIDGET_URL ?? "");
const cdnUrl = String(args["cdn-url"] ?? process.env.AZURE_DEPLOYED_CDN_URL ?? "");
const sdkPath = String(args["sdk-path"] ?? "/widget-sdk/v1/loader.js");

const report = {
  schema_version: "1.0",
  environment,
  timestamp: utcTimestamp(),
  checks: [],
  overall_status: "not_run",
};

async function check(name, url, expectedStatus = 200) {
  if (!url) {
    report.checks.push({ name, status: "skipped", reason: "url_not_configured" });
    return;
  }
  if (!url.startsWith("https://")) {
    report.checks.push({ name, status: "failed", reason: "url_must_be_https" });
    return;
  }
  try {
    const response = await fetch(url, { method: "GET", redirect: "manual" });
    report.checks.push({ name, url, status: response.status === expectedStatus ? "passed" : "failed", http_status: response.status });
  } catch (error) {
    report.checks.push({ name, url, status: "failed", reason: error instanceof Error ? error.message : "unknown_error" });
  }
}

await check("api_live", apiUrl ? `${apiUrl.replace(/\/$/, "")}/health/live` : "");
await check("api_ready", apiUrl ? `${apiUrl.replace(/\/$/, "")}/health/ready` : "");
await check("web", baseUrl);
await check("widget_iframe", widgetUrl ? `${widgetUrl.replace(/\/$/, "")}/embed/index.html` : "");
await check("sdk_major_alias", cdnUrl ? `${cdnUrl.replace(/\/$/, "")}${sdkPath}` : "");

if (report.checks.every((check) => check.status === "skipped")) report.overall_status = "skipped_no_urls";
else if (report.checks.every((check) => check.status === "passed" || check.status === "skipped")) report.overall_status = "passed";
else report.overall_status = "failed";

writeJson(join(repoRoot, "artifacts/azure-deployment", environment, "smoke-report.json"), report);
console.log(JSON.stringify(report, null, 2));
if (report.overall_status === "failed") process.exit(1);

