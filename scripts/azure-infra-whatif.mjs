#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import process from "node:process";

const repoRoot = dirname(fileURLToPath(new URL("../package.json", import.meta.url)));
const environment = process.argv[2] ?? "staging";
if (!["staging", "pilot"].includes(environment)) {
  console.error("Usage: npm run infra:azure:whatif -- <staging|pilot>");
  process.exit(1);
}

const location = process.env.AZURE_LOCATION ?? "australiaeast";
const subscriptionId = process.env.AZURE_SUBSCRIPTION_ID;
const postgresPassword = process.env.AZURE_POSTGRES_ADMIN_PASSWORD;
const parameterFile = join(repoRoot, `infrastructure/azure/environments/${environment}.bicepparam`);
const parameterDirectory = dirname(parameterFile);

if (!subscriptionId || !postgresPassword) {
  console.log("Azure what-if was not run because credentials/secure parameters are not configured.");
  console.log("Required environment variables: AZURE_SUBSCRIPTION_ID and AZURE_POSTGRES_ADMIN_PASSWORD.");
  console.log("Non-destructive what-if uses a temporary .bicepparam overlay with readEnvironmentVariable('AZURE_POSTGRES_ADMIN_PASSWORD').");
  process.exit(0);
}

const account = spawnSync("az", ["account", "set", "--subscription", subscriptionId], {
  stdio: "inherit",
  shell: process.platform === "win32",
});
if (account.status !== 0) {
  process.exit(account.status ?? 1);
}

let temporaryParameterFile = null;
try {
  temporaryParameterFile = createTemporaryParameterFile();
  const temporaryParameterArgument = relative(repoRoot, temporaryParameterFile);
  const result = spawnSync("az", buildWhatIfArgs(location, temporaryParameterArgument), {
    cwd: repoRoot,
    stdio: "inherit",
    shell: process.platform === "win32",
    env: process.env,
  });
  process.exitCode = result.status ?? 1;
} finally {
  if (temporaryParameterFile) {
    rmSync(temporaryParameterFile, { force: true });
  }
}

function createTemporaryParameterFile() {
  if (!existsSync(parameterFile)) {
    throw new Error(`Azure parameter file not found: ${relative(repoRoot, parameterFile)}`);
  }
  const suffix = `${process.pid}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const temporaryParameterFile = join(parameterDirectory, `.${environment}-${suffix}.generated.bicepparam`);
  const baseContent = readFileSync(parameterFile, "utf8").replace(/\s+$/, "");
  const overlay = [
    baseContent,
    "",
    "param postgresAdministratorPassword = readEnvironmentVariable('AZURE_POSTGRES_ADMIN_PASSWORD')",
    "",
  ].join("\n");
  writeFileSync(temporaryParameterFile, overlay, { encoding: "utf8", flag: "wx" });
  return temporaryParameterFile;
}

function buildWhatIfArgs(region, parametersPath) {
  return [
    "deployment",
    "sub",
    "what-if",
    "--location",
    region,
    "--parameters",
    parametersPath,
  ];
}
