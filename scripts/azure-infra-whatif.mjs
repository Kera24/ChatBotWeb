#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import process from "node:process";

const environment = process.argv[2] ?? "staging";
if (!["staging", "pilot"].includes(environment)) {
  console.error("Usage: npm run infra:azure:whatif -- <staging|pilot>");
  process.exit(1);
}

const location = process.env.AZURE_LOCATION ?? "australiaeast";
const subscriptionId = process.env.AZURE_SUBSCRIPTION_ID;
const postgresPassword = process.env.AZURE_POSTGRES_ADMIN_PASSWORD;
const parameterFile = `infrastructure/azure/environments/${environment}.bicepparam`;

const command = [
  "az", "deployment", "sub", "what-if",
  "--location", location,
  "--template-file", "infrastructure/azure/main.bicep",
  "--parameters", parameterFile,
  "--parameters", "postgresAdministratorPassword=$AZURE_POSTGRES_ADMIN_PASSWORD",
];

if (!subscriptionId || !postgresPassword) {
  console.log("Azure what-if was not run because credentials/secure parameters are not configured.");
  console.log("Required environment variables: AZURE_SUBSCRIPTION_ID and AZURE_POSTGRES_ADMIN_PASSWORD.");
  console.log(`Non-destructive command to run after azure/login: ${command.join(" ")}`);
  process.exit(0);
}

const account = spawnSync("az", ["account", "set", "--subscription", subscriptionId], {
  stdio: "inherit",
  shell: process.platform === "win32",
});
if (account.status !== 0) {
  process.exit(account.status ?? 1);
}

const result = spawnSync(command[0], command.slice(1), {
  stdio: "inherit",
  shell: process.platform === "win32",
  env: process.env,
});
process.exit(result.status ?? 1);
