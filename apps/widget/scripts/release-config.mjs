import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");

export const API_VERSION = "v1";
export const RELEASE_SCHEMA_VERSION = 1;
export const DEFAULT_RELEASE_CHANNEL = "pilot";
export const DEFAULT_RELEASE_ENVIRONMENT = "pilot";

export const DEFAULT_ORIGINS = Object.freeze({
  WIDGET_PUBLIC_ORIGIN: "https://widget.example.com",
  WIDGET_PUBLIC_API_ORIGIN: "https://widget-api.example.com",
  WIDGET_SDK_PUBLIC_ORIGIN: "https://cdn.example.com",
});

export function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

export function sdkPackageJson() {
  return readJson(resolve(repoRoot, "packages/widget-sdk/package.json"));
}

export function sdkSourceVersion() {
  const value = sdkPackageJson().version;
  assertSemver(value, "packages/widget-sdk/package.json version");
  return value;
}

export function sdkProtocolMetadata() {
  const text = readFileSync(resolve(repoRoot, "packages/widget-sdk/src/version.ts"), "utf8");
  const sdkMajor = matchNumberConstant(text, "SDK_MAJOR_VERSION");
  const protocolMajor = matchNumberConstant(text, "WIDGET_PROTOCOL_VERSION");
  return { sdkMajor, protocolMajor };
}

export function matchNumberConstant(text, name) {
  const match = text.match(new RegExp(`export\\s+const\\s+${name}\\s*=\\s*(\\d+)\\s+as\\s+const`));
  if (!match) throw new Error(`Missing ${name} constant`);
  return Number(match[1]);
}

export function assertSemver(value, label = "version") {
  if (typeof value !== "string" || !/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/.test(value)) {
    throw new Error(`${label} must be a valid semantic version`);
  }
}

export function normalizeOrigin(input, { productionLike, name }) {
  if (typeof input !== "string" || input.trim() === "") {
    throw new Error(`${name} is required`);
  }
  let parsed;
  try {
    parsed = new URL(input);
  } catch {
    throw new Error(`${name} must be a valid URL origin`);
  }
  if (parsed.username || parsed.password) throw new Error(`${name} must not include credentials`);
  if (parsed.pathname !== "/" || parsed.search || parsed.hash) throw new Error(`${name} must be an origin without path, query, or fragment`);
  const hostname = parsed.hostname.toLowerCase();
  const isLocal =
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    hostname === "::1" ||
    hostname.endsWith(".localhost");
  if (productionLike && parsed.protocol !== "https:") throw new Error(`${name} must use HTTPS for staging/pilot/production`);
  if (productionLike && isLocal) throw new Error(`${name} must not use localhost for staging/pilot/production`);
  if (!productionLike && !["http:", "https:"].includes(parsed.protocol)) throw new Error(`${name} must use HTTP or HTTPS`);
  parsed.pathname = "/";
  return parsed.origin;
}

export function validateReleaseConfig(env = process.env) {
  const releaseEnvironment = env.WIDGET_RELEASE_ENVIRONMENT || DEFAULT_RELEASE_ENVIRONMENT;
  const releaseChannel = env.WIDGET_RELEASE_CHANNEL || DEFAULT_RELEASE_CHANNEL;
  const productionLike = ["staging", "pilot", "production"].includes(releaseEnvironment);
  if (!["development", "test", "staging", "pilot", "production"].includes(releaseEnvironment)) {
    throw new Error("WIDGET_RELEASE_ENVIRONMENT must be development, test, staging, pilot, or production");
  }
  if (!["pilot", "stable"].includes(releaseChannel)) {
    throw new Error("WIDGET_RELEASE_CHANNEL must be pilot or stable");
  }
  const origins = Object.fromEntries(
    Object.entries(DEFAULT_ORIGINS).map(([name, fallback]) => [
      name,
      normalizeOrigin(env[name] || fallback, { productionLike, name }),
    ]),
  );
  if (origins.WIDGET_PUBLIC_ORIGIN === origins.WIDGET_PUBLIC_API_ORIGIN) {
    throw new Error("WIDGET_PUBLIC_ORIGIN and WIDGET_PUBLIC_API_ORIGIN must be distinct");
  }
  const sdkVersion = sdkSourceVersion();
  const { sdkMajor, protocolMajor } = sdkProtocolMetadata();
  return Object.freeze({
    schema_version: RELEASE_SCHEMA_VERSION,
    release_environment: releaseEnvironment,
    release_channel: releaseChannel,
    sdk_version: sdkVersion,
    sdk_major: sdkMajor,
    protocol_major: protocolMajor,
    api_version: API_VERSION,
    origins,
  });
}

export function sha256File(path) {
  const hash = createHash("sha256");
  hash.update(readFileSync(path));
  return hash.digest("hex");
}

export function sriSha384File(path) {
  const hash = createHash("sha384");
  hash.update(readFileSync(path));
  return `sha384-${hash.digest("base64")}`;
}

export function gitCommit() {
  try {
    return execFileSync("git", ["rev-parse", "--short=12", "HEAD"], { cwd: repoRoot, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
    return "unknown";
  }
}

export function utcTimestamp() {
  return new Date().toISOString();
}

export function repoPath(...parts) {
  return resolve(repoRoot, ...parts);
}
