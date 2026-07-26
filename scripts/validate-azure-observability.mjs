#!/usr/bin/env node
import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";

const root = process.cwd();
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
  if (!content.includes(needle)) failures.push(`${name} must contain ${needle}`);
}

function requireNotContains(name, content, needle) {
  if (content.includes(needle)) failures.push(`${name} must not contain ${needle}`);
}

const alertManifest = JSON.parse(read("deployment/widget/alerts.json") || "{}");
const alertIds = new Set((alertManifest.alerts || []).map((alert) => alert.alert_id));
const severityMap = { critical: 1, incident: 2, warning: 3 };
for (const alert of alertManifest.alerts || []) {
  if (!(alert.severity in severityMap)) failures.push(`Alert ${alert.alert_id} has unmapped severity ${alert.severity}`);
  if (!alert.runbook) failures.push(`Alert ${alert.alert_id} is missing runbook`);
}

const main = read("infrastructure/azure/main.bicep");
const monitoring = read("infrastructure/azure/modules/monitoring.bicep");
const containerApps = read("infrastructure/azure/modules/container-apps.bicep");
const alerts = read("infrastructure/azure/modules/monitoring-alerts.bicep");
const diagnostics = read("infrastructure/azure/modules/diagnostics.bicep");
const apiTelemetry = read("apps/api/app/operations/telemetry.py");
const apiLogging = read("apps/api/app/operations/logging.py");
const sdkVite = read("packages/widget-sdk/vite.config.ts");
const widgetVite = read("apps/widget/vite.config.ts");

requireContains("main.bicep", main, "modules/monitoring-alerts.bicep");
requireContains("main.bicep", main, "actionGroupEmailReceivers");
requireContains("monitoring.bicep", monitoring, "Microsoft.OperationalInsights/workspaces");
requireContains("monitoring.bicep", monitoring, "Microsoft.Insights/components");
requireContains("monitoring.bicep", monitoring, "retentionInDays");
requireContains("container-apps.bicep", containerApps, "APPLICATIONINSIGHTS_CONNECTION_STRING");
requireContains("container-apps.bicep", containerApps, "AZURE_MONITOR_OPEN_TELEMETRY_ENABLED");
requireContains("monitoring-alerts.bicep", alerts, "Microsoft.Insights/actionGroups");
requireContains("monitoring-alerts.bicep", alerts, "Microsoft.Insights/webtests");
requireContains("monitoring-alerts.bicep", alerts, "widget-public-api-5xx-spike");
requireContains("monitoring-alerts.bicep", alerts, "widget-origin-denial-spike");
requireContains("diagnostics.bicep", diagnostics, "ContainerAppConsoleLogs");
requireContains("diagnostics.bicep", diagnostics, "FrontDoorAccessLog");
requireContains("diagnostics.bicep", diagnostics, "PostgreSQLLogs");
requireContains("diagnostics.bicep", diagnostics, "AuditEvent");
requireContains("api telemetry", apiTelemetry, "normalise_route");
requireContains("api telemetry", apiTelemetry, "Azure Monitor OpenTelemetry");
requireContains("api telemetry", apiTelemetry, "safe_attributes");
for (const secret of ["authorization", "cookie", "session_token", "preview_grant", "draft_configuration", "provider_prompt", "database_url", "connection_string"]) {
  requireContains("api logging", apiLogging, secret);
}
requireContains("SDK vite", sdkVite, "sourcemap: false");
requireContains("widget vite", widgetVite, "sourcemap: false");

const queriesDir = path.join(root, "infrastructure/azure/monitoring/queries");
const queryFiles = existsSync(queriesDir) ? readdirSync(queriesDir).filter((file) => file.endsWith(".kql")) : [];
if (queryFiles.length < 6) failures.push("Expected at least six KQL query files.");
for (const file of queryFiles) {
  const content = read(`infrastructure/azure/monitoring/queries/${file}`);
  for (const forbidden of ["message_body", "answer", "citation_text", "session_token", "Authorization", "Cookie", "preview_token", "draft_configuration"]) {
    requireNotContains(file, content, forbidden);
  }
}
const workbook = read("infrastructure/azure/monitoring/workbooks/controlled-pilot-observability.workbook.json");
try {
  JSON.parse(workbook);
} catch (error) {
  failures.push(`Workbook JSON is invalid: ${error.message}`);
}
requireContains("workbook", workbook, "Release comparison");
requireContains("workbook", workbook, "Synthetic availability");

for (const requiredAlert of ["widget-public-api-5xx-spike", "widget-origin-denial-spike", "widget-public-service-unavailable", "widget-synthetic-smoke-failure"]) {
  if (!alertIds.has(requiredAlert)) failures.push(`Provider-neutral alert manifest missing ${requiredAlert}`);
}
if (!alerts.includes("widget-public-service-unavailable")) warnings.push("API availability is represented by webtests; static alert linkage is documented but not separately expressed as a scheduled query.");

if (failures.length) {
  console.error("Azure observability validation failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}
console.log("Azure observability validation passed.");
for (const warning of warnings) console.warn(`Warning: ${warning}`);
