#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { join } from "node:path";
import { assertEnvironment, parseArgs, repoRoot, utcTimestamp, writeJson } from "./azure-release-lib.mjs";

const args = parseArgs(process.argv.slice(2));
const environment = String(args.environment ?? args._[0] ?? "staging");
assertEnvironment(environment);
if (environment !== "staging") throw new Error("Synthetic widget bootstrap wrapper only supports staging.");
if (process.env.APP_ENV !== "staging") throw new Error("APP_ENV=staging is required.");
if (process.env.WIDGET_STAGING_SYNTHETIC_BOOTSTRAP !== "1") throw new Error("WIDGET_STAGING_SYNTHETIC_BOOTSTRAP=1 is required.");

const execute = Boolean(args.execute || args._.includes("execute"));
const namePrefix = String(args["name-prefix"] ?? process.env.AZURE_NAME_PREFIX ?? "yoranix");
const resourceGroup = String(args["resource-group"] ?? process.env.AZURE_RESOURCE_GROUP ?? `${namePrefix}-staging-rg`);
const jobName = String(args.job ?? process.env.AZURE_SYNTHETIC_WIDGET_BOOTSTRAP_JOB ?? `${namePrefix}-staging-job-synthetic-widgets`);
const image = String(args.image ?? process.env.API_IMAGE_REF ?? process.env.AZURE_API_IMAGE ?? "");

const report = {
  schema_version: "1.0",
  environment,
  timestamp: utcTimestamp(),
  mode: execute ? "execute" : "dry_run",
  resource_group: resourceGroup,
  job: jobName,
  status: "planned",
};

if (execute) {
  if (!image) throw new Error("API image digest/reference is required to create the synthetic widget bootstrap job.");
  const envVars = ["APP_ENV=staging", "WIDGET_STAGING_SYNTHETIC_BOOTSTRAP=1"];
  if (process.env.STAGING_API_URL) envVars.push(`STAGING_API_URL=${process.env.STAGING_API_URL}`);
  const update = spawnSync("az", [
    "containerapp", "job", "update",
    "--name", jobName,
    "--resource-group", resourceGroup,
    "--image", image,
    "--command", "python",
    "--args", "-m", "app.operations.staging_synthetic_widgets",
    "--set-env-vars", ...envVars,
  ], { stdio: "inherit", shell: process.platform === "win32" });
  if (update.status !== 0) throw new Error("Failed to update staging synthetic widget bootstrap job. Ensure the job exists and uses managed Key Vault configuration.");
  const start = spawnSync("az", ["containerapp", "job", "start", "--name", jobName, "--resource-group", resourceGroup], { stdio: "inherit", shell: process.platform === "win32" });
  if (start.status !== 0) throw new Error("Failed to start staging synthetic widget bootstrap job.");
  report.status = "started";
} else {
  report.status = "dry_run_ready";
}

writeJson(join(repoRoot, "artifacts/azure-staging-validation", "synthetic-widgets-bootstrap-job.json"), report);
console.log(JSON.stringify(report, null, 2));
