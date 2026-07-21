#!/usr/bin/env node
import { existsSync } from "node:fs";
import { join } from "node:path";
import { parseArgs, readJson, resolveRepoPath, validateImageRef, validateWidgetRelease } from "./azure-release-lib.mjs";

const args = parseArgs(process.argv.slice(2));
const manifestPath = resolveRepoPath(String(args.manifest ?? args._[0] ?? "artifacts/deployment-release/manifest.json"));
const expectedSource = args["expected-source-environment"] ? String(args["expected-source-environment"]) : null;
const requirePassedGates = args["require-passed-gates"] !== false;
const manifest = readJson(manifestPath);
const failures = [];

if (manifest.schema_version !== "1.0") failures.push("schema_version must be 1.0");
if (expectedSource && manifest.environment !== expectedSource) failures.push(`manifest environment must be ${expectedSource}`);
try { validateImageRef(manifest.api_image?.ref, "API image ref"); } catch (error) { failures.push(error.message); }
try { validateImageRef(manifest.web_image?.ref, "Web image ref"); } catch (error) { failures.push(error.message); }
if (!manifest.git_sha || manifest.git_sha === "unknown") failures.push("git_sha is required");
if (!manifest.db_migration_head) failures.push("db_migration_head is required");
if (!manifest.protocol_major) failures.push("protocol_major is required");
if (!manifest.public_api_version) failures.push("public_api_version is required");

if (requirePassedGates) {
  for (const gate of ["admin_readiness", "pilot_verification", "pilot_readiness"]) {
    if (manifest.gates?.[gate] !== "passed") failures.push(`${gate} gate must be passed`);
  }
}

const releaseDir = resolveRepoPath(String(args["release-dir"] ?? args._[1] ?? "artifacts/widget-release"));
if (existsSync(releaseDir)) {
  try {
    const { manifest: widgetManifest } = validateWidgetRelease(releaseDir);
    if (widgetManifest.sdk_version !== manifest.widget_release?.sdk_version) failures.push("widget release SDK version differs from deployment manifest");
    if (widgetManifest.checksums?.immutable_loader_sha256 !== manifest.widget_release?.sdk_immutable_loader_sha256) failures.push("widget immutable SDK checksum differs from deployment manifest");
    if (widgetManifest.checksums?.iframe_html_sha256 !== manifest.widget_release?.iframe_html_sha256) failures.push("widget iframe checksum differs from deployment manifest");
  } catch (error) {
    failures.push(error.message);
  }
}

if (failures.length > 0) {
  console.error("Deployment manifest validation failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log(JSON.stringify({
  status: "passed",
  release_id: manifest.release_id,
  git_sha: manifest.git_sha,
  api_image: manifest.api_image.ref,
  web_image: manifest.web_image.ref,
  sdk_version: manifest.widget_release.sdk_version,
  db_migration_head: manifest.db_migration_head,
}, null, 2));

