#!/usr/bin/env node
// Generic (non-Azure) deployment smoke test for the single-VPS deployment.
// Adapted from scripts/azure-deployed-smoke.mjs - same check logic, but
// takes plain --base-url/--api-url/--widget-url flags instead of Azure
// environment/naming conventions, so it works against any docker-compose.prod.yml
// deployment (VPS today, any future host tomorrow).
//
// Usage:
//   node scripts/vps-smoke.mjs --base-url https://app.example.com \
//     --api-url https://api.example.com --widget-url https://widget.example.com
//
// If only --base-url is given, --api-url/--widget-url default to it (useful
// when API and widget share the web domain behind path-based routing).

import { join } from "node:path";
import { parseArgs, repoRoot, writeJson } from "./azure-release-lib.mjs";

const args = parseArgs(process.argv.slice(2));
const baseUrl = String(args["base-url"] ?? process.env.VPS_DEPLOYED_BASE_URL ?? "");
const apiUrl = String(args["api-url"] ?? process.env.VPS_DEPLOYED_API_URL ?? baseUrl);
const widgetUrl = String(args["widget-url"] ?? process.env.VPS_DEPLOYED_WIDGET_URL ?? "");
const sdkPath = String(args["sdk-path"] ?? "/widget-sdk/v1/loader.js");
const allowInsecure = Boolean(args["allow-insecure"]);

const report = {
  schema_version: "1.0",
  target: "vps",
  timestamp: new Date().toISOString(),
  checks: [],
  overall_status: "not_run",
};

async function check(name, url, { expectedStatus = 200 } = {}) {
  if (!url) {
    report.checks.push({ name, status: "skipped", reason: "url_not_configured" });
    return;
  }
  if (!allowInsecure && !url.startsWith("https://")) {
    report.checks.push({ name, status: "failed", reason: "url_must_be_https" });
    return;
  }
  try {
    const response = await fetch(url, { method: "GET", redirect: "manual" });
    report.checks.push({
      name,
      url,
      status: response.status === expectedStatus ? "passed" : "failed",
      http_status: response.status,
    });
  } catch (error) {
    report.checks.push({ name, url, status: "failed", reason: error instanceof Error ? error.message : "unknown_error" });
  }
}

await check("api_live", apiUrl ? `${apiUrl.replace(/\/$/, "")}/health/live` : "");
await check("api_ready", apiUrl ? `${apiUrl.replace(/\/$/, "")}/health/ready` : "");
await check("web", baseUrl);
await check("widget_iframe", widgetUrl ? `${widgetUrl.replace(/\/$/, "")}/embed/index.html` : "");
await check("sdk_loader", widgetUrl ? `${widgetUrl.replace(/\/$/, "")}${sdkPath}` : "");

if (report.checks.every((c) => c.status === "skipped")) report.overall_status = "skipped_no_urls";
else if (report.checks.every((c) => c.status === "passed" || c.status === "skipped")) report.overall_status = "passed";
else report.overall_status = "failed";

writeJson(join(repoRoot, "artifacts/vps-deployment/smoke-report.json"), report);
console.log(JSON.stringify(report, null, 2));
if (report.overall_status === "failed") process.exit(1);
