#!/usr/bin/env node
import process from "node:process";
import { baseEvidence, parseStagingArgs, requiredEnv, writeStagingEvidence } from "./azure-staging-lib.mjs";

const { environment, execute } = parseStagingArgs();
const required = [
  "STAGING_APP_URL",
  "STAGING_API_URL",
  "STAGING_WIDGET_URL",
  "STAGING_CDN_URL",
  "STAGING_WIDGET_PUBLIC_KEY_ALPHA",
  "STAGING_WIDGET_PUBLIC_KEY_BETA",
  "STAGING_SYNTHETIC_ALPHA_ORIGIN",
  "STAGING_SYNTHETIC_BETA_ORIGIN",
];
const missing = requiredEnv(required);

const report = {
  ...baseEvidence("live_browser_smoke", environment),
  mode: execute ? "execute" : "dry_run",
  required_configuration: Object.fromEntries(required.map((name) => [name, Boolean(process.env[name])])),
  scenarios: [
    "load immutable SDK",
    "mount iframe and complete handshake",
    "fetch real public config",
    "create and reuse session",
    "send bounded synthetic Alpha/Beta messages",
    "positive same-tenant retrieval",
    "negative cross-tenant retrieval",
    "cross-widget session rejection",
    "origin denial",
    "no cookies, token postMessage, or sensitive console output",
  ],
  status: missing.length === 0 && execute ? "ready_for_playwright_execution" : "blocked_missing_prerequisites",
  blockers: missing.map((name) => `${name} is not configured.`),
};

if (missing.length === 0 && execute) {
  report.status = "not_executed_by_repository_script";
  report.note = "Run the dedicated staging workflow or operator runbook with Playwright installed and approved staging credentials. This wrapper records configuration readiness without embedding secrets.";
}

writeStagingEvidence("browser-smoke.json", report);
console.log(JSON.stringify(report, null, 2));
if (execute && report.status === "blocked_missing_prerequisites") process.exit(1);
