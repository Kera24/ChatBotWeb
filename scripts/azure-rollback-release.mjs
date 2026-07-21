#!/usr/bin/env node
import { join } from "node:path";
import { parseArgs, readJson, repoRoot, resolveRepoPath, utcTimestamp, validateManifestCompatibility, writeJson } from "./azure-release-lib.mjs";

const args = parseArgs(process.argv.slice(2));
const currentPath = args.current || args._[0] ? resolveRepoPath(String(args.current ?? args._[0])) : null;
const targetPath = args.to || args._[1] ? resolveRepoPath(String(args.to ?? args._[1])) : null;
if (!currentPath || !targetPath) {
  throw new Error("Usage: npm run azure:rollback:plan -- --current <current-manifest> --to <target-manifest>");
}
const current = readJson(currentPath);
const target = readJson(targetPath);
const compatibilityErrors = validateManifestCompatibility(current, target);

const plan = {
  schema_version: "1.0",
  mode: "dry_run",
  timestamp: utcTimestamp(),
  from_release_id: current.release_id,
  to_release_id: target.release_id,
  from_git_sha: current.git_sha,
  to_git_sha: target.git_sha,
  compatibility_status: compatibilityErrors.length === 0 ? "compatible" : "blocked",
  compatibility_errors: compatibilityErrors,
  actions: [],
  required_smoke: [
    "health/live",
    "health/ready",
    "web availability",
    "SDK major alias availability",
    "widget iframe availability",
    "synthetic config/session/message smoke",
  ],
};

if (compatibilityErrors.length === 0) {
  plan.actions.push({ type: "api", action: "switch_or_redeploy_container_app_revision", image: target.api_image.ref });
  plan.actions.push({ type: "web", action: "switch_or_redeploy_container_app_revision", image: target.web_image.ref });
  plan.actions.push({ type: "widget", action: "restore_iframe_static_artifact", iframe_html_sha256: target.widget_release.iframe_html_sha256 });
  plan.actions.push({ type: "sdk", action: "repoint_major_alias", alias_path: target.widget_release.sdk_major_alias_path, target_sdk_version: target.widget_release.sdk_version });
}

writeJson(join(repoRoot, "artifacts/azure-deployment/rollback-plan.json"), plan);
console.log(JSON.stringify(plan, null, 2));
if (compatibilityErrors.length > 0) process.exit(1);

