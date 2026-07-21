#!/usr/bin/env node
import { join } from "node:path";
import {
  assertEnvironment,
  currentAlembicHead,
  gitSha,
  parseArgs,
  repoRoot,
  resolveRepoPath,
  statusFromReport,
  utcTimestamp,
  validateImageRef,
  validateWidgetRelease,
  writeJson,
} from "./azure-release-lib.mjs";

const args = parseArgs(process.argv.slice(2));
const environment = String(args.environment ?? args._[0] ?? "staging");
assertEnvironment(environment);

const releaseDir = resolveRepoPath(String(args["release-dir"] ?? "artifacts/widget-release"));
const outDir = resolveRepoPath(String(args.out ?? "artifacts/deployment-release"));
const apiImage = validateImageRef(String(args["api-image"] ?? args._[1] ?? process.env.API_IMAGE_REF ?? `chatbotweb-api:${gitSha()}`), "API image ref");
const webImage = validateImageRef(String(args["web-image"] ?? args._[2] ?? process.env.WEB_IMAGE_REF ?? `chatbotweb-web:${gitSha()}`), "Web image ref");
const dryRun = args["dry-run"] !== false;
const { manifest: widgetManifest } = validateWidgetRelease(releaseDir);
const alembicHead = currentAlembicHead();

const adminReadinessPath = join(repoRoot, "artifacts/widget-admin-readiness/report.json");
const pilotVerificationPath = join(repoRoot, "artifacts/widget-pilot-verification/report.json");
const pilotReadinessPath = join(repoRoot, "artifacts/widget-pilot-readiness/report.json");

const manifest = {
  schema_version: "1.0",
  release_id: `${gitSha()}-${environment}`,
  git_sha: gitSha(),
  timestamp: utcTimestamp(),
  environment,
  mode: dryRun ? "dry_run" : "release_candidate",
  api_image: {
    repository: apiImage.split("@")[0].split(":")[0],
    ref: apiImage,
    digest: apiImage.includes("@sha256:") ? apiImage.split("@sha256:")[1] : null,
    immutable: apiImage.includes("@sha256:") || !apiImage.endsWith(":latest"),
  },
  web_image: {
    repository: webImage.split("@")[0].split(":")[0],
    ref: webImage,
    digest: webImage.includes("@sha256:") ? webImage.split("@sha256:")[1] : null,
    immutable: webImage.includes("@sha256:") || !webImage.endsWith(":latest"),
  },
  widget_release: {
    sdk_version: widgetManifest.sdk_version,
    sdk_major: widgetManifest.sdk_major,
    sdk_immutable_loader_path: widgetManifest.immutable_loader_path,
    sdk_major_alias_path: widgetManifest.major_alias_path,
    sdk_immutable_loader_sha256: widgetManifest.checksums.immutable_loader_sha256,
    sdk_major_alias_sha256: widgetManifest.checksums.major_alias_loader_sha256,
    sdk_immutable_loader_sri: widgetManifest.sri?.immutable_loader ?? null,
    iframe_html_path: widgetManifest.iframe_html_path,
    iframe_html_sha256: widgetManifest.checksums.iframe_html_sha256,
    gzip_bytes: widgetManifest.gzip_bytes,
  },
  protocol_major: widgetManifest.protocol_major,
  public_api_version: widgetManifest.api_version,
  db_migration_head: alembicHead,
  gates: {
    admin_readiness: statusFromReport(adminReadinessPath),
    pilot_verification: statusFromReport(pilotVerificationPath),
    pilot_readiness: statusFromReport(pilotReadinessPath),
  },
  promotion: {
    build_once_promote_same_artifact: true,
    web_runtime_config_note: "Next.js container receives NEXT_PUBLIC_API_BASE_URL from environment in the current deployment model; review if build-time public values diverge.",
    widget_environment_note: "Widget release artifacts are generated from configured public origins; staging and pilot artifacts must not be cross-promoted when embedded origins differ.",
  },
  required_post_deploy_checks: [
    "api_health_live",
    "api_health_ready",
    "web_availability",
    "sdk_immutable_availability",
    "sdk_major_alias_availability",
    "widget_iframe_availability",
    "staging_live_browser_smoke_or_B4_gate",
  ],
};

writeJson(join(outDir, "manifest.json"), manifest);
writeJson(join(repoRoot, "artifacts/azure-deployment", environment, "report.json"), {
  schema_version: "1.0",
  release_manifest_id: manifest.release_id,
  git_sha: manifest.git_sha,
  environment,
  timestamp: utcTimestamp(),
  api_digest: manifest.api_image.digest,
  web_digest: manifest.web_image.digest,
  sdk_version: manifest.widget_release.sdk_version,
  widget_iframe_html_sha256: manifest.widget_release.iframe_html_sha256,
  infrastructure_deployment_id: dryRun ? "not_run_dry_run" : "pending",
  migration_status: dryRun ? "not_run_dry_run" : "pending",
  api_revision: dryRun ? "not_deployed_dry_run" : "pending",
  web_revision: dryRun ? "not_deployed_dry_run" : "pending",
  static_publication_status: dryRun ? "not_run_dry_run" : "pending",
  health_status: dryRun ? "not_run_dry_run" : "pending",
  post_deploy_smoke_status: dryRun ? "not_run_dry_run" : "pending",
  overall_status: dryRun ? "dry_run_ready" : "pending",
});

console.log(JSON.stringify({
  status: "ok",
  manifest: "artifacts/deployment-release/manifest.json",
  report: `artifacts/azure-deployment/${environment}/report.json`,
  environment,
  git_sha: manifest.git_sha,
  db_migration_head: alembicHead,
  api_image: apiImage,
  web_image: webImage,
}, null, 2));



