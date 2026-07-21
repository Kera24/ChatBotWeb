import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

export const repoRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
export const allowedEnvironments = new Set(["staging", "pilot"]);

export function parseArgs(argv) {
  const parsed = { _: [] };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (!arg.startsWith("--")) {
      parsed._.push(arg);
      continue;
    }
    const key = arg.slice(2);
    const next = argv[index + 1];
    if (!next || next.startsWith("--")) {
      parsed[key] = true;
      continue;
    }
    parsed[key] = next;
    index += 1;
  }
  return parsed;
}

export function resolveRepoPath(value) {
  return isAbsolute(value) ? value : join(repoRoot, value);
}

export function assertEnvironment(environment) {
  if (!allowedEnvironments.has(environment)) {
    throw new Error(`Unsupported environment: ${environment}. Expected staging or pilot.`);
  }
}

export function assertFile(path, label = "file") {
  if (!existsSync(path) || !statSync(path).isFile()) {
    throw new Error(`Missing ${label}: ${path}`);
  }
}

export function assertDirectory(path, label = "directory") {
  if (!existsSync(path) || !statSync(path).isDirectory()) {
    throw new Error(`Missing ${label}: ${path}`);
  }
}

export function readJson(path) {
  assertFile(path, "JSON file");
  return JSON.parse(readFileSync(path, "utf8"));
}

export function writeJson(path, value) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

export function sha256File(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

export function gitSha() {
  const result = spawnSync("git", ["rev-parse", "--short=12", "HEAD"], { cwd: repoRoot, encoding: "utf8" });
  if (result.status !== 0) return "unknown";
  return result.stdout.trim();
}

export function utcTimestamp() {
  return new Date().toISOString();
}

export function currentAlembicHead() {
  const versionsDir = join(repoRoot, "apps/api/alembic/versions");
  assertDirectory(versionsDir, "Alembic versions directory");
  const revisions = new Map();
  const downRevisions = new Set();
  for (const fileName of readdirSync(versionsDir).filter((name) => name.endsWith(".py"))) {
    const content = readFileSync(join(versionsDir, fileName), "utf8");
    const revision = content.match(/revision:\s*str\s*=\s*["']([^"']+)["']/)?.[1];
    const down = content.match(/down_revision:\s*str\s*\|\s*None\s*=\s*["']([^"']+)["']/)?.[1];
    if (revision) revisions.set(revision, fileName);
    if (down) downRevisions.add(down);
  }
  const heads = [...revisions.keys()].filter((revision) => !downRevisions.has(revision));
  if (heads.length !== 1) {
    throw new Error(`Expected exactly one Alembic head, found ${heads.length}: ${heads.join(", ")}`);
  }
  return heads[0];
}

export function validateWidgetRelease(releaseDir) {
  const manifestPath = join(releaseDir, "manifest.json");
  const manifest = readJson(manifestPath);
  const immutableLoader = join(releaseDir, "sdk", `v${manifest.sdk_version}`, "loader.js");
  const aliasLoader = join(releaseDir, "sdk", `v${manifest.sdk_major}`, "loader.js");
  const iframeHtml = join(releaseDir, "widget", "index.html");
  assertFile(immutableLoader, "immutable SDK loader");
  assertFile(aliasLoader, "major alias SDK loader");
  assertFile(iframeHtml, "widget iframe HTML");
  const immutableSha = sha256File(immutableLoader);
  const aliasSha = sha256File(aliasLoader);
  const htmlSha = sha256File(iframeHtml);
  if (manifest.checksums?.immutable_loader_sha256 !== immutableSha) throw new Error("Immutable SDK checksum mismatch.");
  if (manifest.checksums?.major_alias_loader_sha256 !== aliasSha) throw new Error("Major alias SDK checksum mismatch.");
  if (manifest.checksums?.iframe_html_sha256 !== htmlSha) throw new Error("Iframe HTML checksum mismatch.");
  return { manifest, manifestPath, immutableLoader, aliasLoader, iframeHtml };
}

export function statusFromReport(path) {
  if (!existsSync(path)) return "missing";
  const report = readJson(path);
  return report.overall_status ?? (report.status === "passed" ? "passed" : "unknown");
}

export function validateImageRef(ref, label) {
  if (!ref) throw new Error(`Missing ${label}.`);
  if (ref.includes(":latest")) throw new Error(`${label} must not use latest.`);
  if (/\s/.test(ref)) throw new Error(`${label} contains whitespace.`);
  return ref;
}

export function safeRelative(path) {
  return relative(repoRoot, path).replaceAll("\\", "/");
}

export function validateManifestCompatibility(current, target) {
  const errors = [];
  if (current.protocol_major !== target.protocol_major) errors.push("protocol_major differs");
  if (current.public_api_version !== target.public_api_version) errors.push("public_api_version differs");
  if (current.db_migration_head !== target.db_migration_head) errors.push("database migration head differs; automatic DB downgrade is not supported");
  return errors;
}

export function listFilesRecursive(root) {
  const files = [];
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    const fullPath = join(root, entry.name);
    if (entry.isDirectory()) files.push(...listFilesRecursive(fullPath));
    else if (entry.isFile()) files.push(fullPath);
  }
  return files;
}

export function mimeTypeFor(path) {
  if (path.endsWith(".html")) return "text/html; charset=utf-8";
  if (path.endsWith(".js")) return "text/javascript; charset=utf-8";
  if (path.endsWith(".css")) return "text/css; charset=utf-8";
  if (path.endsWith(".json")) return "application/json; charset=utf-8";
  if (path.endsWith(".svg")) return "image/svg+xml";
  if (path.endsWith(".png")) return "image/png";
  if (path.endsWith(".jpg") || path.endsWith(".jpeg")) return "image/jpeg";
  if (path.endsWith(".webp")) return "image/webp";
  return "application/octet-stream";
}

export function cacheControlFor(relativePath, manifest) {
  const normalized = `/${relativePath.replaceAll("\\", "/")}`;
  if (normalized.startsWith(`/widget-sdk/v${manifest.sdk_version}/`)) return manifest.cache_policies.immutable_sdk;
  if (normalized === `/widget-sdk/v${manifest.sdk_major}/loader.js`) return manifest.cache_policies.sdk_major_alias;
  if (normalized === "/embed/index.html" || normalized.endsWith("/index.html")) return manifest.cache_policies.iframe_html;
  if (normalized.startsWith("/assets/")) return manifest.cache_policies.iframe_hashed_assets;
  return "public, max-age=300, must-revalidate";
}
