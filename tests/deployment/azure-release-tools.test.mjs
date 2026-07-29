import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { chmodSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";

const root = process.cwd();
const fixtureRoot = join(root, "artifacts/test-azure-release-tools");

function run(args, options = {}) {
  return spawnSync(process.execPath, args, {
    cwd: root,
    encoding: "utf8",
    ...options,
  });
}

function sha(value) {
  return createHash("sha256").update(value).digest("hex");
}

function write(path, value) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, value, "utf8");
}


function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function staticPublicationReport() {
  return readJson(join(root, "artifacts/azure-deployment/staging/static-publication-report.json"));
}

function fixtureRelease() {
  rmSync(fixtureRoot, { recursive: true, force: true });
  const release = join(fixtureRoot, "release");
  const loader = "console.log('loader');\n";
  const html = "<html><body><script src=\"/assets/index-AbCd1234.js\"></script></body></html>\n";
  const js = "console.log('widget');\n";
  write(join(release, "sdk/v0.1.0-foundation.0/loader.js"), loader);
  write(join(release, "sdk/v1/loader.js"), loader);
  write(join(release, "sdk/v1/alias.json"), JSON.stringify({ alias: "v1", target_sdk_version: "0.1.0-foundation.0" }));
  write(join(release, "widget/index.html"), html);
  write(join(release, "widget/assets/index-AbCd1234.js"), js);
  write(join(release, "manifest.json"), JSON.stringify({
    schema_version: 1,
    release_channel: "pilot",
    release_environment: "pilot",
    sdk_version: "0.1.0-foundation.0",
    sdk_major: 1,
    protocol_major: 1,
    api_version: "v1",
    build_commit: "fixture",
    build_timestamp: "2026-07-22T00:00:00.000Z",
    immutable_loader_path: "/widget-sdk/v0.1.0-foundation.0/loader.js",
    major_alias_path: "/widget-sdk/v1/loader.js",
    iframe_html_path: "/embed/index.html",
    checksums: {
      immutable_loader_sha256: sha(loader),
      major_alias_loader_sha256: sha(loader),
      iframe_html_sha256: sha(html),
    },
    sri: { immutable_loader: "sha384-fixture" },
    gzip_bytes: { immutable_loader: 1, major_alias_loader: 1, iframe_assets: { "index-AbCd1234.js": 1 } },
    cache_policies: {
      immutable_sdk: "public, max-age=31536000, immutable",
      sdk_major_alias: "public, max-age=300, must-revalidate",
      iframe_html: "no-cache",
      iframe_hashed_assets: "public, max-age=31536000, immutable",
    },
  }, null, 2));
  return release;
}

test("deployment manifest records immutable images and Alembic head", () => {
  const release = fixtureRelease();
  const result = run([
    "scripts/build-deployment-release.mjs",
    "--environment", "staging",
    "--release-dir", release,
    "--api-image", "example.azurecr.io/chatbotweb-api@sha256:aaaaaaaa",
    "--web-image", "example.azurecr.io/chatbotweb-web@sha256:bbbbbbbb",
  ]);
  assert.equal(result.status, 0, result.stderr || result.stdout);
  const manifest = JSON.parse(readFileSync(join(root, "artifacts/deployment-release/manifest.json"), "utf8"));
  assert.equal(manifest.environment, "staging");
  assert.equal(manifest.api_image.digest, "aaaaaaaa");
  assert.equal(manifest.web_image.digest, "bbbbbbbb");
  assert.equal(manifest.db_migration_head, "0012_widget_knowledge_preview_installation");
});

test("deployment manifest rejects latest image tags", () => {
  const release = fixtureRelease();
  const result = run([
    "scripts/build-deployment-release.mjs",
    "--environment", "staging",
    "--release-dir", release,
    "--api-image", "example.azurecr.io/chatbotweb-api:latest",
    "--web-image", "example.azurecr.io/chatbotweb-web:abc",
  ]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /latest/);
});

test("static publisher copies local files and blocks immutable checksum conflicts", () => {
  const release = fixtureRelease();
  const destination = join(fixtureRoot, "published");
  const ok = run([
    "scripts/publish-azure-widget-release.mjs",
    "--environment", "staging",
    "--release-dir", release,
    "--local-destination", destination,
  ]);
  assert.equal(ok.status, 0, ok.stderr || ok.stdout);
  assert.ok(existsSync(join(destination, "widget-sdk/v0.1.0-foundation.0/loader.js")));
  assert.ok(existsSync(join(destination, "widget-sdk/v1/loader.js")));
  write(join(destination, "widget-sdk/v0.1.0-foundation.0/loader.js"), "changed\n");
  const conflict = run([
    "scripts/publish-azure-widget-release.mjs",
    "--environment", "staging",
    "--release-dir", release,
    "--local-destination", destination,
  ]);
  assert.notEqual(conflict.status, 0);
  assert.match(conflict.stderr, /Immutable release collision|Immutable artifact conflict/);
});


function createFakeAzureCli(blobRoot) {
  const bin = join(fixtureRoot, "fake-az-bin");
  mkdirSync(bin, { recursive: true });
  const fake = join(bin, "fake-az.mjs");
  write(fake, `import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
const args = process.argv.slice(2);
const root = process.env.FAKE_AZURE_BLOB_ROOT;
function value(flag) {
  const index = args.indexOf(flag);
  return index >= 0 ? args[index + 1] : "";
}
function blobPath() {
  return join(root, value("--account-name"), value("--container-name"), value("--name"));
}
if (args.join(" ").startsWith("storage blob exists")) {
  process.stdout.write(existsSync(blobPath()) ? "true\\n" : "false\\n");
  process.exit(0);
}
if (args.join(" ").startsWith("storage blob download")) {
  const source = blobPath();
  if (!existsSync(source)) {
    process.stderr.write("BlobNotFound\\n");
    process.exit(1);
  }
  const target = value("--file");
  mkdirSync(dirname(target), { recursive: true });
  copyFileSync(source, target);
  process.exit(0);
}
if (args.join(" ").startsWith("storage blob upload")) {
  const target = blobPath();
  const overwrite = value("--overwrite") === "true";
  if (existsSync(target) && !overwrite) {
    process.stderr.write("BlobAlreadyExists\\n");
    process.exit(1);
  }
  mkdirSync(dirname(target), { recursive: true });
  copyFileSync(value("--file"), target);
  process.exit(0);
}
process.stderr.write("Unsupported fake az command: " + args.join(" ") + "\\n");
process.exit(1);
`);
  const azCmd = join(bin, "az.cmd");
  write(azCmd, `@echo off\r\nnode "%~dp0fake-az.mjs" %*\r\n`);
  const azSh = join(bin, "az");
  write(azSh, `#!/usr/bin/env sh\nnode "$(dirname "$0")/fake-az.mjs" "$@"\n`);
  chmodSync(azSh, 0o755);
  return bin;
}

function runPublisherWithFakeAzure(release, blobRoot) {
  const fakeBin = createFakeAzureCli(blobRoot);
  return run([
    "scripts/publish-azure-widget-release.mjs",
    "--environment", "staging",
    "--release-dir", release,
    "--storage-account", "fixturestorage",
    "--execute",
  ], {
    env: {
      ...process.env,
      FAKE_AZURE_BLOB_ROOT: blobRoot,
      AZURE_CLI_PATH: join(fakeBin, "fake-az.mjs"),
      PATH: `${fakeBin}${process.platform === "win32" ? ";" : ":"}${process.env.PATH}`,
    },
  });
}

test("static publisher uploads new immutable blobs before mutable aliases", () => {
  const release = fixtureRelease();
  const blobRoot = join(fixtureRoot, "azure-new");

  const result = runPublisherWithFakeAzure(release, blobRoot);

  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.ok(existsSync(join(blobRoot, "fixturestorage/$web/widget-sdk/v0.1.0-foundation.0/loader.js")));
  assert.ok(existsSync(join(blobRoot, "fixturestorage/$web/widget-sdk/v1/loader.js")));
  const report = staticPublicationReport();
  const statuses = report.publication_results.map((entry) => entry.status);
  assert.ok(statuses.includes("uploaded"));
  assert.ok(statuses.includes("alias_updated"));
  const firstMutable = report.publication_results.findIndex((entry) => entry.mutable);
  const lastImmutable = report.publication_results.findLastIndex((entry) => !entry.mutable);
  assert.ok(lastImmutable < firstMutable);
});

test("static publisher treats identical existing immutable Azure blobs as idempotent", () => {
  const release = fixtureRelease();
  const blobRoot = join(fixtureRoot, "azure-identical");
  assert.equal(runPublisherWithFakeAzure(release, blobRoot).status, 0);

  const rerun = runPublisherWithFakeAzure(release, blobRoot);

  assert.equal(rerun.status, 0, rerun.stderr || rerun.stdout);
  const report = staticPublicationReport();
  assert.ok(report.publication_results.some((entry) => entry.destination_path === "widget-sdk/v0.1.0-foundation.0/loader.js" && entry.status === "already_exists_identical"));
});

test("static publisher fails conflicting immutable Azure blobs before alias replacement", () => {
  const release = fixtureRelease();
  const blobRoot = join(fixtureRoot, "azure-conflict");
  const aliasPath = join(blobRoot, "fixturestorage/$web/widget-sdk/v1/loader.js");
  write(join(blobRoot, "fixturestorage/$web/widget-sdk/v0.1.0-foundation.0/loader.js"), "conflict\n");
  write(aliasPath, "old alias\n");

  const result = runPublisherWithFakeAzure(release, blobRoot);

  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /Immutable release collision/);
  assert.equal(readFileSync(aliasPath, "utf8"), "old alias\n");
  const report = staticPublicationReport();
  assert.ok(report.publication_results.some((entry) => entry.status === "collision_failed"));
  assert.ok(!report.publication_results.some((entry) => entry.destination_path === "widget-sdk/v1/loader.js" && entry.status === "alias_updated"));
});

test("static publisher replaces mutable Azure alias after immutable verification", () => {
  const release = fixtureRelease();
  const blobRoot = join(fixtureRoot, "azure-alias");
  write(join(blobRoot, "fixturestorage/$web/widget-sdk/v0.1.0-foundation.0/loader.js"), "console.log('loader');\n");
  write(join(blobRoot, "fixturestorage/$web/assets/index-AbCd1234.js"), "console.log('widget');\n");
  const aliasPath = join(blobRoot, "fixturestorage/$web/widget-sdk/v1/loader.js");
  write(aliasPath, "old alias\n");

  const result = runPublisherWithFakeAzure(release, blobRoot);

  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.equal(readFileSync(aliasPath, "utf8"), "console.log('loader');\n");
  const report = staticPublicationReport();
  assert.ok(report.publication_results.some((entry) => entry.destination_path === "widget-sdk/v1/loader.js" && entry.status === "alias_updated"));
});
test("rollback planner blocks migration-incompatible target", () => {
  const current = join(fixtureRoot, "current.json");
  const target = join(fixtureRoot, "target.json");
  const base = {
    schema_version: "1.0",
    release_id: "current",
    git_sha: "a",
    protocol_major: 1,
    public_api_version: "v1",
    db_migration_head: "head-a",
    api_image: { ref: "api@sha256:a" },
    web_image: { ref: "web@sha256:a" },
    widget_release: { iframe_html_sha256: "a", sdk_major_alias_path: "/widget-sdk/v1/loader.js", sdk_version: "0.1.0" },
  };
  write(current, JSON.stringify(base));
  write(target, JSON.stringify({ ...base, release_id: "target", db_migration_head: "head-b" }));
  const result = run(["scripts/azure-rollback-release.mjs", "--current", current, "--to", target]);
  assert.notEqual(result.status, 0);
  assert.match(result.stdout, /database migration head differs/);
});

test("deployed smoke safely skips when no endpoints are configured", () => {
  const result = run(["scripts/azure-deployed-smoke.mjs", "--environment", "staging"]);
  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.match(result.stdout, /skipped_no_urls/);
});

test("Azure deployment workflows keep OIDC, approvals, concurrency, and no latest policy", () => {
  const staging = readFileSync(join(root, ".github/workflows/azure-deploy-staging.yml"), "utf8");
  const pilot = readFileSync(join(root, ".github/workflows/azure-promote-pilot.yml"), "utf8");
  const rollback = readFileSync(join(root, ".github/workflows/azure-rollback.yml"), "utf8");
  for (const [name, content] of [["staging", staging], ["pilot", pilot], ["rollback", rollback]]) {
    assert.match(content, /id-token: write/, `${name} workflow must use OIDC permission`);
    assert.match(content, /concurrency:/, `${name} workflow must define concurrency`);
    assert.doesNotMatch(content, /pull_request_target/, `${name} workflow must not use privileged PR target`);
    assert.doesNotMatch(content, /:latest/, `${name} workflow must not deploy latest`);
  }
  assert.match(pilot, /environment: production-pilot/);
  assert.match(pilot, /Download staged release artifact/);
  assert.match(rollback, /execute/);
});

test("staging deployment workflow defaults to infrastructure-only and uses secure what-if parameters", () => {
  const staging = readFileSync(join(root, ".github/workflows/azure-deploy-staging.yml"), "utf8");
  assert.match(staging, /deploy_infrastructure:[\s\S]*?default: "true"/);
  assert.match(staging, /deploy_application:[\s\S]*?default: "false"/);
  assert.match(staging, /mktemp infrastructure\/azure\/environments\/\.staging-deploy-XXXXXX\.generated\.bicepparam/);
  assert.match(staging, /readEnvironmentVariable\('AZURE_POSTGRES_ADMIN_PASSWORD'\)/);
  assert.match(staging, /trap cleanup EXIT/);
  assert.match(staging, /az deployment sub create[\s\S]*--parameters "\$TEMP_BICEPPARAM"/);
  assert.doesNotMatch(staging, /--template-file infrastructure\/azure\/main\.bicep/);
  assert.doesNotMatch(staging, /postgresAdministratorPassword="?\$AZURE_POSTGRES_ADMIN_PASSWORD/);
  assert.match(staging, /AZURE_ACR_NAME is blank/);
  assert.match(staging, /az acr show --name "\$ACR_NAME"/);
  assert.match(staging, /az acr login --name "\$\{\{ steps\.azure_resources\.outputs\.acr_name \}\}"/);
  assert.match(staging, /ACR_LOGIN_SERVER: \$\{\{ steps\.azure_resources\.outputs\.acr_login_server \}\}/);
});
