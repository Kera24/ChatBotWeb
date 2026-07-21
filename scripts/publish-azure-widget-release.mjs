#!/usr/bin/env node
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
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
  status: "planned",
};

if (localDestination) {
  for (const item of plan) {
    const source = join(repoRoot, item.source);
    const target = join(localDestination, item.destination_path);
    if (!item.mutable && existsSync(target)) {
      const existingChecksum = sha256File(target);
      if (existingChecksum !== item.checksum_sha256) {
        throw new Error(`Immutable artifact conflict at ${item.destination_path}. Existing checksum differs.`);
      }
      continue;
    }
    mkdirSync(dirname(target), { recursive: true });
    copyFileSync(source, target);
  }
  report.status = "local_published";
  report.local_destination = safeRelative(localDestination);
} else if (execute) {
  if (!storageAccount) throw new Error("--execute requires --storage-account or AZURE_WIDGET_STORAGE_ACCOUNT.");
  for (const item of plan) {
    const source = join(repoRoot, item.source);
    const uploadArgs = [
      "storage", "blob", "upload",
      "--auth-mode", "login",
      "--account-name", storageAccount,
      "--container-name", container,
      "--file", source,
      "--name", item.destination_path,
      "--content-type", item.content_type,
      "--content-cache-control", item.cache_control,
      "--overwrite", item.mutable ? "true" : "false",
    ];
    const result = spawnSync("az", uploadArgs, { stdio: "inherit", shell: process.platform === "win32" });
    if (result.status !== 0) throw new Error(`Azure Blob upload failed for ${item.destination_path}.`);
  }
  report.status = "uploaded";
} else {
  report.status = "dry_run_ready";
}

writeJson(join(repoRoot, "artifacts/azure-deployment", environment, "static-publication-report.json"), {
  ...report,
  planned_uploads: plan,
});
console.log(JSON.stringify(report, null, 2));



