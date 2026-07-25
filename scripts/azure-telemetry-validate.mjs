#!/usr/bin/env node
import process from "node:process";
import { baseEvidence, collectAzurePrerequisites, parseStagingArgs, requiredEnv, writeStagingEvidence } from "./azure-staging-lib.mjs";

const { environment, execute } = parseStagingArgs();
const prerequisites = collectAzurePrerequisites();
const required = ["AZURE_LOG_ANALYTICS_WORKSPACE", "AZURE_APPLICATION_INSIGHTS_NAME", "AZURE_RESOURCE_GROUP"];
const missing = requiredEnv(required);

const report = {
  ...baseEvidence("telemetry_validation", environment),
  mode: execute ? "execute" : "dry_run",
  prerequisites,
  required_configuration: Object.fromEntries(required.map((name) => [name, Boolean(process.env[name])])),
  checks: [
    "API request telemetry by request ID",
    "environment and release tags",
    "dependency telemetry",
    "structured operational events",
    "privacy canary absence from traces, exceptions, custom events, dependency data, and logs",
    "workbook and KQL query execution",
  ],
  status: prerequisites.status === "ready" && missing.length === 0 && execute ? "ready_for_live_queries" : "blocked_missing_prerequisites",
  blockers: [...prerequisites.blockers, ...missing.map((name) => `${name} is not configured.`)],
};

if (report.status === "ready_for_live_queries") {
  report.status = "not_executed_by_repository_script";
  report.note = "Live KQL/App Insights queries require deployed staging traffic and are executed from the protected staging workflow/runbook.";
}

writeStagingEvidence("telemetry.json", report);
console.log(JSON.stringify(report, null, 2));
if (execute && report.status === "blocked_missing_prerequisites") process.exit(1);
