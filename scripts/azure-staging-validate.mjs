#!/usr/bin/env node
import process from "node:process";
import {
  baseEvidence,
  collectAzurePrerequisites,
  commandResult,
  parseStagingArgs,
  writeStagingEvidence,
} from "./azure-staging-lib.mjs";

const { args, environment, execute } = parseStagingArgs();
const prerequisites = collectAzurePrerequisites();
const deploymentName = String(args["deployment-name"] ?? `task-068b4-staging-${Date.now()}`);
const resourceGroup = String(process.env.AZURE_RESOURCE_GROUP ?? "yoranix-staging-rg");

const infrastructure = {
  ...baseEvidence("infrastructure", environment),
  deployment_name: deploymentName,
  resource_group: resourceGroup,
  region: process.env.AZURE_LOCATION ?? "australiaeast",
  mode: execute ? "execute" : "dry_run",
  prerequisites,
  what_if: { status: "not_run" },
  deployment: { status: "not_run" },
  resource_names: {
    key_vault: process.env.AZURE_KEY_VAULT_NAME ?? null,
    acr: process.env.AZURE_ACR_NAME ?? null,
    container_apps_environment: process.env.AZURE_CONTAINER_APPS_ENVIRONMENT ?? null,
    api_container_app: process.env.AZURE_API_CONTAINER_APP ?? "yoranix-staging-ca-api",
    web_container_app: process.env.AZURE_WEB_CONTAINER_APP ?? "yoranix-staging-ca-web",
    log_analytics_workspace: process.env.AZURE_LOG_ANALYTICS_WORKSPACE ?? null,
    application_insights: process.env.AZURE_APPLICATION_INSIGHTS_NAME ?? null,
    storage_account: process.env.AZURE_WIDGET_STORAGE_ACCOUNT ?? null,
    postgresql_host: process.env.AZURE_POSTGRES_HOST ?? null,
    front_door_endpoint: process.env.STAGING_FRONT_DOOR_ENDPOINT ?? null,
  },
};

if (prerequisites.status === "ready") {
  const whatIfArgs = [
    "deployment",
    "sub",
    "what-if",
    "--location",
    infrastructure.region,
    "--template-file",
    "infrastructure/azure/main.bicep",
    "--parameters",
    "infrastructure/azure/environments/staging.bicepparam",
    "--parameters",
    "postgresAdministratorPassword=$AZURE_POSTGRES_ADMIN_PASSWORD",
  ];
  if (execute) {
    const whatIf = commandResult("az", whatIfArgs, { env: process.env });
    infrastructure.what_if = {
      status: whatIf.status === 0 ? "completed" : "failed",
      exit_code: whatIf.status,
      summary: summarizeWhatIf(whatIf.stdout),
      error: whatIf.status === 0 ? null : firstLine(whatIf.stderr || whatIf.stdout),
    };
    if (whatIf.status !== 0) {
      infrastructure.deployment.status = "blocked_by_what_if_failure";
    } else {
      infrastructure.deployment.status = "not_executed_by_repository_script";
      infrastructure.deployment.note =
        "TASK-068B4 repository harness captured what-if evidence. Live deployment remains in the protected workflow/operator runbook.";
    }
  } else {
    infrastructure.what_if = {
      status: "planned_not_executed",
      command: redactCommand(whatIfArgs),
    };
    infrastructure.deployment.status = "dry_run_only";
  }
} else {
  infrastructure.what_if.status = "blocked_missing_prerequisites";
  infrastructure.what_if.blockers = prerequisites.blockers;
  infrastructure.deployment.status = "blocked_missing_prerequisites";
}

const report = {
  ...baseEvidence("staging_validation_report", environment),
  classification:
    infrastructure.deployment.status === "blocked_missing_prerequisites"
      ? "staging deployment blocked before execution"
      : execute
        ? "staging deployment evidence incomplete"
        : "repository configured; staging live validation not executed",
  overall_status:
    infrastructure.deployment.status === "blocked_missing_prerequisites" ? "blocked_missing_prerequisites" : "configured",
  azure_prerequisites: prerequisites,
  infrastructure: {
    status: infrastructure.deployment.status,
    evidence_path: "artifacts/azure-staging-validation/infrastructure.json",
  },
  migration: { status: "not_executed" },
  application_deployment: { status: "not_executed" },
  static_publication: { status: "not_executed" },
  live_browser_smoke: { status: "not_executed" },
  telemetry: { status: "not_executed" },
  alerts: { status: "not_executed" },
  rollback: { status: "not_executed" },
  backup_restore: { status: "not_executed" },
  notes: [
    "No production-pilot deployment was attempted.",
    "No customer data or real customer widget was used.",
    "Evidence files intentionally contain operational metadata only.",
  ],
};

writeStagingEvidence("infrastructure.json", infrastructure);
writeStagingEvidence("report.json", report);
console.log(JSON.stringify(report, null, 2));

if (execute && report.overall_status !== "configured") process.exit(1);

function summarizeWhatIf(stdout) {
  const text = String(stdout ?? "");
  return {
    contains_delete: /\bDelete\b/i.test(text),
    contains_replace: /\bReplace\b/i.test(text),
    create_count: countWord(text, "Create"),
    modify_count: countWord(text, "Modify"),
    delete_count: countWord(text, "Delete"),
    replace_count: countWord(text, "Replace"),
  };
}

function countWord(text, word) {
  return (String(text).match(new RegExp(`\\b${word}\\b`, "gi")) ?? []).length;
}

function redactCommand(parts) {
  return ["az", ...parts].map((part) => (String(part).includes("postgresAdministratorPassword=") ? "postgresAdministratorPassword=<redacted>" : part));
}

function firstLine(value) {
  return String(value ?? "").split(/\r?\n/).find(Boolean)?.trim() ?? "";
}
