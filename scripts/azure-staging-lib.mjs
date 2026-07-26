import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import process from "node:process";
import { gitSha, parseArgs, repoRoot, utcTimestamp } from "./azure-release-lib.mjs";
export { repoRoot };

export const stagingEvidenceDir = join(repoRoot, "artifacts/azure-staging-validation");

const sensitiveKeyPattern =
  /(secret|password|token|connection.?string|authorization|cookie|session|preview|grant|key|credential|private)/i;
const sensitiveValuePattern =
  /(InstrumentationKey=|AccountKey=|SharedAccessSignature=|postgres(?:ql)?:\/\/|redis:\/\/|Bearer\s+|session_token=|preview[_-]?grant=)/i;

export function assertStagingOnly(environment) {
  if (environment !== "staging") {
    throw new Error(`TASK-068B4 only supports direct execution against staging. Received: ${environment || "<empty>"}.`);
  }
}

export function parseStagingArgs(argv = process.argv.slice(2)) {
  const args = parseArgs(argv);
  const environment = String(args.environment ?? args._[0] ?? "staging");
  assertStagingOnly(environment);
  return { args, environment, execute: Boolean(args.execute || args._.includes("execute")) };
}

export function redact(value) {
  if (Array.isArray(value)) return value.map((entry) => redact(entry));
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, entry]) => [
        key,
        sensitiveKeyPattern.test(key) ? "<redacted>" : redact(entry),
      ]),
    );
  }
  if (typeof value === "string") {
    if (sensitiveValuePattern.test(value)) return "<redacted>";
    return value.replace(/(sig|token|grant|session_token)=([^&\s]+)/gi, "$1=<redacted>");
  }
  return value;
}

export function writeStagingEvidence(fileName, payload) {
  const path = join(stagingEvidenceDir, fileName);
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, `${JSON.stringify(redact(payload), null, 2)}\n`, "utf8");
  return path;
}

export function commandResult(command, args = [], options = {}) {
  return spawnSync(command, args, {
    cwd: repoRoot,
    encoding: "utf8",
    shell: process.platform === "win32",
    ...options,
  });
}

export function commandVersion(command, args = ["--version"]) {
  const result = commandResult(command, args);
  return {
    available: result.status === 0,
    status: result.status,
    version: result.status === 0 ? firstLine(result.stdout || result.stderr) : null,
    error: result.status === 0 ? null : firstLine(result.stderr || result.stdout || `${command} unavailable`),
  };
}

export function gitFullSha() {
  const result = commandResult("git", ["rev-parse", "HEAD"]);
  return result.status === 0 ? result.stdout.trim() : gitSha();
}

export function safeJsonFromCommand(command, args) {
  const result = commandResult(command, args);
  if (result.status !== 0) {
    return { ok: false, error: firstLine(result.stderr || result.stdout || "command failed") };
  }
  try {
    return { ok: true, value: JSON.parse(result.stdout) };
  } catch (error) {
    return { ok: false, error: `Invalid JSON from ${command}: ${error.message}` };
  }
}

export function collectAzurePrerequisites() {
  const azureCli = commandVersion("az", ["--version"]);
  const bicep = azureCli.available ? commandVersion("az", ["bicep", "version"]) : { available: false, version: null, error: "Azure CLI unavailable" };
  const account = azureCli.available ? safeJsonFromCommand("az", ["account", "show", "--output", "json"]) : { ok: false, error: "Azure CLI unavailable" };
  const env = {
    AZURE_SUBSCRIPTION_ID: Boolean(process.env.AZURE_SUBSCRIPTION_ID),
    AZURE_TENANT_ID: Boolean(process.env.AZURE_TENANT_ID),
    AZURE_LOCATION: process.env.AZURE_LOCATION ?? "australiaeast",
    AZURE_RESOURCE_GROUP: process.env.AZURE_RESOURCE_GROUP ?? null,
    AZURE_KEY_VAULT_NAME: process.env.AZURE_KEY_VAULT_NAME ?? null,
    AZURE_POSTGRES_ADMIN_PASSWORD: Boolean(process.env.AZURE_POSTGRES_ADMIN_PASSWORD),
  };
  const blockers = [];
  if (!azureCli.available) blockers.push("Azure CLI is not available.");
  if (!bicep.available) blockers.push("Azure Bicep CLI is not available.");
  if (!process.env.AZURE_SUBSCRIPTION_ID) blockers.push("AZURE_SUBSCRIPTION_ID is not configured.");
  if (!process.env.AZURE_POSTGRES_ADMIN_PASSWORD) blockers.push("AZURE_POSTGRES_ADMIN_PASSWORD is not configured.");
  if (!account.ok) blockers.push(`Azure account is not selected: ${account.error}`);
  if (account.ok && process.env.AZURE_SUBSCRIPTION_ID && account.value?.id !== process.env.AZURE_SUBSCRIPTION_ID) {
    blockers.push("Selected Azure subscription does not match AZURE_SUBSCRIPTION_ID.");
  }
  return {
    azure_cli: azureCli,
    bicep,
    account: account.ok
      ? {
          id: account.value?.id ?? null,
          tenant_id: account.value?.tenantId ?? null,
          name: account.value?.name ?? null,
        }
      : { error: account.error },
    environment_variables: env,
    blockers,
    status: blockers.length === 0 ? "ready" : "blocked_missing_prerequisites",
  };
}

export function baseEvidence(kind, environment = "staging") {
  assertStagingOnly(environment);
  return {
    schema_version: "1.0",
    task: "TASK-068B4",
    kind,
    environment,
    git_sha: gitFullSha(),
    timestamp: utcTimestamp(),
  };
}

export function requiredEnv(names) {
  return names.filter((name) => !process.env[name]);
}

export function readJsonIfExists(path) {
  if (!existsSync(path)) return null;
  return JSON.parse(readFileSync(path, "utf8"));
}

function firstLine(value) {
  return String(value ?? "").split(/\r?\n/).find(Boolean)?.trim() ?? "";
}
