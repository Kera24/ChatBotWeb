#!/usr/bin/env node
import process from "node:process";
import { baseEvidence, collectAzurePrerequisites, parseStagingArgs, requiredEnv, writeStagingEvidence } from "./azure-staging-lib.mjs";

const { environment, execute } = parseStagingArgs();
const prerequisites = collectAzurePrerequisites();
const required = ["AZURE_RESOURCE_GROUP", "AZURE_STAGING_ACTION_GROUP_NAME"];
const missing = requiredEnv(required);

const report = {
  ...baseEvidence("alert_validation", environment),
  mode: execute ? "execute" : "dry_run",
  prerequisites,
  required_configuration: Object.fromEntries(required.map((name) => [name, Boolean(process.env[name])])),
  checks: [
    "staging action group receiver test",
    "alert scopes point at staging resources",
    "severity and runbook tags match provider-neutral alert manifest",
    "synthetic smoke failure routes to staging-only operational path",
  ],
  status: prerequisites.status === "ready" && missing.length === 0 && execute ? "ready_for_live_alert_test" : "blocked_missing_prerequisites",
  blockers: [...prerequisites.blockers, ...missing.map((name) => `${name} is not configured.`)],
};

if (report.status === "ready_for_live_alert_test") {
  report.status = "not_executed_by_repository_script";
  report.note = "Use the staging workflow/runbook to send a controlled action-group test notification or temporary staging-only alert.";
}

writeStagingEvidence("alerts.json", report);
console.log(JSON.stringify(report, null, 2));
if (execute && report.status === "blocked_missing_prerequisites") process.exit(1);
