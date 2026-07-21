#!/usr/bin/env node
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { assertEnvironment, parseArgs, repoRoot, utcTimestamp, validateImageRef, writeJson } from "./azure-release-lib.mjs";

const args = parseArgs(process.argv.slice(2));
const environment = String(args.environment ?? args._[0] ?? "staging");
assertEnvironment(environment);
const execute = Boolean(args.execute || args._.includes("execute"));
const image = validateImageRef(String(args.image ?? args._[1] ?? process.env.API_IMAGE_REF ?? ""), "migration image");
const jobName = String(args.job ?? process.env.AZURE_MIGRATION_JOB_NAME ?? `yoranix-${environment}-job-migrate`);
const resourceGroup = String(args["resource-group"] ?? process.env.AZURE_RESOURCE_GROUP ?? `yoranix-${environment}-rg`);

const report = {
  schema_version: "1.0",
  environment,
  timestamp: utcTimestamp(),
  mode: execute ? "execute" : "dry_run",
  migration_job: jobName,
  resource_group: resourceGroup,
  image,
  status: "planned",
};

if (execute) {
  const update = spawnSync("az", [
    "containerapp", "job", "update",
    "--name", jobName,
    "--resource-group", resourceGroup,
    "--image", image,
  ], { stdio: "inherit", shell: process.platform === "win32" });
  if (update.status !== 0) throw new Error("Failed to update migration job image.");

  const start = spawnSync("az", [
    "containerapp", "job", "start",
    "--name", jobName,
    "--resource-group", resourceGroup,
  ], { encoding: "utf8", shell: process.platform === "win32" });
  if (start.status !== 0) {
    process.stderr.write(start.stderr);
    throw new Error("Failed to start migration job.");
  }
  report.execution = start.stdout.trim();
  report.status = "started";
} else {
  report.status = "dry_run_ready";
}

writeJson(join(repoRoot, "artifacts/azure-deployment", environment, "migration-report.json"), report);
console.log(JSON.stringify(report, null, 2));



