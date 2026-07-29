#!/usr/bin/env node
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, relative } from "node:path";
import { spawnSync } from "node:child_process";
import {
  assertEnvironment,
  cacheControlFor,
  listFilesRecursive,
  mimeTypeFor,
  parseArgs,
  repoRoot,
  resolveRepoPath,
  safeRelative,
  sha256File,
  utcTimestamp,
  validateWidgetRelease,
  writeJson,
} from "./azure-release-lib.mjs";

const args = parseArgs(process.argv.slice(2));
const environment = String(args.environment ?? args._[0] ?? "staging");
assertEnvironment(environment);
const execute = Boolean(args.execute || args._.includes("execute"));
const releaseDir = resolveRepoPath(String(args["release-dir"] ?? "artifacts/widget-release"));
const localDestination = args["local-destination"] || args._[1] ? resolveRepoPath(String(args["local-destination"] ?? args._[1])) : null;
const storageAccount = String(args["storage-account"] ?? process.env.AZURE_WIDGET_STORAGE_ACCOUNT ?? "");
const container = String(args.container ?? "$web");
const { manifest } = validateWidgetRelease(releaseDir);

const plan = [];
function addUpload(source, destinationPath, mutable) {
  const checksum = sha256File(source);
  const relativeDestination = destinationPath.replace(/^\/+/, "");
  plan.push({
    source: safeRelative(source),
    destination_path: relativeDestination,
    checksum_sha256: checksum,
    mutable,
    cache_control: cacheControlFor(relativeDestination, manifest),
    content_type: mimeTypeFor(source),
  });
}

addUpload(join(releaseDir, "sdk", `v${manifest.sdk_version}`, "loader.js"), manifest.immutable_loader_path, false);
addUpload(join(releaseDir, "widget", "index.html"), manifest.iframe_html_path, true);
for (const file of listFilesRecursive(join(releaseDir, "widget", "assets"))) {
  addUpload(file, `assets/${relative(join(releaseDir, "widget", "assets"), file).replaceAll("\\", "/")}`, false);
}
addUpload(join(releaseDir, "sdk", `v${manifest.sdk_major}`, "loader.js"), manifest.major_alias_path, true);
addUpload(join(releaseDir, "sdk", `v${manifest.sdk_major}`, "alias.json"), `/widget-sdk/v${manifest.sdk_major}/alias.json`, true);
addUpload(join(releaseDir, "manifest.json"), "/release/manifest.json", true);

const report = {
  schema_version: "1.0",
  environment,
  timestamp: utcTimestamp(),
  mode: execute ? "execute" : "dry_run",
  release_sdk_version: manifest.sdk_version,
  sdk_major_alias: `v${manifest.sdk_major}`,
  storage_account: storageAccount || "not_configured",
  container,
  immutable_uploads: plan.filter((item) => !item.mutable).length,
  mutable_uploads: plan.filter((item) => item.mutable).length,
  upload_order: plan.map((item) => item.destination_path),
  publication_results: [],
  status: "planned",
};

function record(item, status, extra = {}) {
  const entry = {
    destination_path: item.destination_path,
    mutable: item.mutable,
    checksum_sha256: item.checksum_sha256,
    status,
    ...extra,
  };
  report.publication_results.push(entry);
  return entry;
}

function immutableCollision(item, existingChecksum) {
  record(item, "collision_failed", { existing_checksum_sha256: existingChecksum });
  throw new Error(
    `Immutable release collision at ${item.destination_path}. `
    + `Existing checksum ${existingChecksum} differs from local checksum ${item.checksum_sha256}.`
  );
}

function runAz(commandArgs, errorMessage, options = {}) {
  const configuredAzureCli = process.env.AZURE_CLI_PATH || "";
  const runWithNode = configuredAzureCli.endsWith(".mjs");
  const azureCli = runWithNode ? process.execPath : configuredAzureCli || (process.platform === "win32" ? "az.cmd" : "az");
  const effectiveArgs = runWithNode ? [configuredAzureCli, ...commandArgs] : commandArgs;
  const result = spawnSync(azureCli, effectiveArgs, {
    encoding: "utf8",
    stdio: options.inherit ? "inherit" : "pipe",
  });
  if (result.error) throw new Error(`${errorMessage}: ${result.error.message}`);
  if (result.status !== 0) {
    const stderr = String(result.stderr ?? "").trim();
    const stdout = String(result.stdout ?? "").trim();
    throw new Error(`${errorMessage}${stderr || stdout ? `: ${stderr || stdout}` : ""}`);
  }
  return String(result.stdout ?? "").trim();
}

function blobExists(item) {
  const output = runAz([
    "storage", "blob", "exists",
    "--auth-mode", "login",
    "--account-name", storageAccount,
    "--container-name", container,
    "--name", item.destination_path,
    "--query", "exists",
    "-o", "tsv",
  ], `Failed to inspect Azure Blob existence for ${item.destination_path}`);
  return output.toLowerCase() === "true";
}

function downloadExistingChecksum(item) {
  const tempDir = mkdtempSync(join(tmpdir(), "widget-blob-"));
  const tempFile = join(tempDir, "existing-blob");
  try {
    runAz([
      "storage", "blob", "download",
      "--auth-mode", "login",
      "--account-name", storageAccount,
      "--container-name", container,
      "--name", item.destination_path,
      "--file", tempFile,
      "--overwrite", "true",
      "--no-progress",
    ], `Failed to download existing Azure Blob for checksum comparison at ${item.destination_path}`);
    return sha256File(tempFile);
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
}

function uploadAzure(item, overwrite) {
  const source = join(repoRoot, item.source);
  runAz([
    "storage", "blob", "upload",
    "--auth-mode", "login",
    "--account-name", storageAccount,
    "--container-name", container,
    "--file", source,
    "--name", item.destination_path,
    "--content-type", item.content_type,
    "--content-cache-control", item.cache_control,
    "--metadata", `sha256=${item.checksum_sha256}`,
    "--overwrite", overwrite ? "true" : "false",
  ], `Azure Blob upload failed for ${item.destination_path}`, { inherit: true });
}

function publishLocalItem(item) {
  const source = join(repoRoot, item.source);
  const target = join(localDestination, item.destination_path);
  if (!item.mutable && existsSync(target)) {
    const existingChecksum = sha256File(target);
    if (existingChecksum !== item.checksum_sha256) immutableCollision(item, existingChecksum);
    record(item, "already_exists_identical");
    return;
  }
  mkdirSync(dirname(target), { recursive: true });
  copyFileSync(source, target);
  record(item, item.mutable ? "alias_updated" : "uploaded");
}

function publishAzureImmutable(item) {
  if (!blobExists(item)) {
    uploadAzure(item, false);
    record(item, "uploaded");
    return;
  }

  const existingChecksum = downloadExistingChecksum(item);
  if (existingChecksum !== item.checksum_sha256) immutableCollision(item, existingChecksum);
  record(item, "already_exists_identical", { existing_checksum_sha256: existingChecksum });
}

function publishAzureMutable(item) {
  uploadAzure(item, true);
  record(item, "alias_updated");
}

function publishItems(publishImmutable, publishMutable) {
  for (const item of plan.filter((entry) => !entry.mutable)) publishImmutable(item);
  for (const item of plan.filter((entry) => entry.mutable)) publishMutable(item);
}

try {
  if (localDestination) {
    publishItems(publishLocalItem, publishLocalItem);
    report.status = "local_published";
    report.local_destination = safeRelative(localDestination);
  } else if (execute) {
    if (!storageAccount) throw new Error("--execute requires --storage-account or AZURE_WIDGET_STORAGE_ACCOUNT.");
    publishItems(publishAzureImmutable, publishAzureMutable);
    report.status = "uploaded";
  } else {
    report.status = "dry_run_ready";
  }
} finally {
  writeJson(join(repoRoot, "artifacts/azure-deployment", environment, "static-publication-report.json"), {
    ...report,
    planned_uploads: plan,
  });
}

console.log(JSON.stringify(report, null, 2));
