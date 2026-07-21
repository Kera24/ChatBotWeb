import { copyFileSync, cpSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { basename, join, relative } from "node:path";
import { gzipSync } from "node:zlib";
import {
  gitCommit,
  repoPath,
  sha256File,
  sriSha384File,
  utcTimestamp,
  validateReleaseConfig,
} from "./release-config.mjs";

const config = validateReleaseConfig();
const outputRoot = repoPath("artifacts/widget-release");
const sdkDist = repoPath("packages/widget-sdk/dist");
const widgetDist = repoPath("apps/widget/dist");
const headersSource = repoPath("deployment/widget/headers.json");

const sdkLoader = join(sdkDist, "yoranix-widget-sdk.global.js");
const widgetIndex = join(widgetDist, "index.html");
const widgetAssets = join(widgetDist, "assets");

assertFile(sdkLoader, "SDK IIFE bundle");
assertFile(widgetIndex, "widget iframe HTML");
assertDirectory(widgetAssets, "widget asset directory");
assertFile(headersSource, "widget header policy");
assertHashedIframeAssets(widgetAssets);

rmSync(outputRoot, { recursive: true, force: true });

const immutableSdkDir = join(outputRoot, "sdk", `v${config.sdk_version}`);
const aliasSdkDir = join(outputRoot, "sdk", `v${config.sdk_major}`);
const widgetOut = join(outputRoot, "widget");
const deploymentOut = join(outputRoot, "deployment");
mkdirSync(immutableSdkDir, { recursive: true });
mkdirSync(aliasSdkDir, { recursive: true });
mkdirSync(widgetOut, { recursive: true });
mkdirSync(deploymentOut, { recursive: true });

const immutableLoader = join(immutableSdkDir, "loader.js");
const aliasLoader = join(aliasSdkDir, "loader.js");
copyFileSync(sdkLoader, immutableLoader);
copyFileSync(sdkLoader, aliasLoader);
copyFileSync(widgetIndex, join(widgetOut, "index.html"));
cpSync(widgetAssets, join(widgetOut, "assets"), { recursive: true });
copyFileSync(headersSource, join(deploymentOut, "headers.json"));

const immutableSha256 = sha256File(immutableLoader);
const aliasSha256 = sha256File(aliasLoader);
const buildCommit = gitCommit();
const buildTimestamp = utcTimestamp();

const aliasManifest = {
  schema_version: 1,
  alias: `v${config.sdk_major}`,
  target_sdk_version: config.sdk_version,
  loader_path: `/widget-sdk/v${config.sdk_major}/loader.js`,
  target_loader_path: `/widget-sdk/v${config.sdk_version}/loader.js`,
  cache_control: "public, max-age=300, must-revalidate",
  sha256: aliasSha256,
  build_commit: buildCommit,
  build_timestamp: buildTimestamp,
};
writeJson(join(aliasSdkDir, "alias.json"), aliasManifest);

const widgetRelease = {
  schema_version: 1,
  release_channel: config.release_channel,
  release_environment: config.release_environment,
  build_commit: buildCommit,
  build_timestamp: buildTimestamp,
  protocol_major: config.protocol_major,
  public_api_version: config.api_version,
  widget_html_cache_control: "no-cache",
};
writeJson(join(widgetOut, "release.json"), widgetRelease);

const manifest = {
  schema_version: config.schema_version,
  release_channel: config.release_channel,
  release_environment: config.release_environment,
  sdk_version: config.sdk_version,
  sdk_major: config.sdk_major,
  protocol_major: config.protocol_major,
  api_version: config.api_version,
  build_commit: buildCommit,
  build_timestamp: buildTimestamp,
  origins: config.origins,
  immutable_loader_path: `/widget-sdk/v${config.sdk_version}/loader.js`,
  major_alias_path: `/widget-sdk/v${config.sdk_major}/loader.js`,
  iframe_html_path: "/embed/index.html",
  iframe_asset_path_pattern: "/assets/*",
  compatibility: {
    sdk_major_alias: `v${config.sdk_major}`,
    supported_protocol_majors: [config.protocol_major],
    public_api_versions: [config.api_version],
    iframe_release_channel: config.release_channel,
  },
  cache_policies: {
    immutable_sdk: "public, max-age=31536000, immutable",
    sdk_major_alias: "public, max-age=300, must-revalidate",
    iframe_html: "no-cache",
    iframe_hashed_assets: "public, max-age=31536000, immutable",
  },
  checksums: {
    immutable_loader_sha256: immutableSha256,
    major_alias_loader_sha256: aliasSha256,
    iframe_html_sha256: sha256File(join(widgetOut, "index.html")),
  },
  sri: {
    immutable_loader: sriSha384File(immutableLoader),
  },
  gzip_bytes: {
    immutable_loader: gzipSize(immutableLoader),
    major_alias_loader: gzipSize(aliasLoader),
    iframe_assets: gzipAssetSummary(join(widgetOut, "assets")),
  },
};
writeJson(join(outputRoot, "manifest.json"), manifest);

process.stdout.write(`Widget release artifacts generated at ${relative(repoPath(), outputRoot)}\n`);
process.stdout.write(`SDK ${config.sdk_version} -> /widget-sdk/v${config.sdk_version}/loader.js\n`);
process.stdout.write(`SDK major alias v${config.sdk_major} -> ${config.sdk_version}\n`);

export function assertHashedIframeAssets(assetsDir) {
  const files = readdirSync(assetsDir).filter((name) => name.endsWith(".js") || name.endsWith(".css"));
  if (files.length === 0) throw new Error("No iframe JavaScript or CSS assets found");
  for (const fileName of files) {
    if (!/-[A-Za-z0-9_-]{6,}\.(js|css)$/.test(fileName)) {
      throw new Error(`Iframe asset is not content-hashed: ${fileName}`);
    }
  }
}

function gzipAssetSummary(assetsDir) {
  return Object.fromEntries(
    readdirSync(assetsDir)
      .filter((name) => name.endsWith(".js") || name.endsWith(".css"))
      .map((name) => [name, gzipSize(join(assetsDir, name))]),
  );
}

function gzipSize(path) {
  return gzipSync(readFileSync(path)).byteLength;
}

function assertFile(path, label) {
  if (!existsSync(path) || !statSync(path).isFile()) throw new Error(`Missing ${label}: ${path}`);
}

function assertDirectory(path, label) {
  if (!existsSync(path) || !statSync(path).isDirectory()) throw new Error(`Missing ${label}: ${path}`);
}

function writeJson(path, value) {
  writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}
