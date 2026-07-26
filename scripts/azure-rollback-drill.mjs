#!/usr/bin/env node
import process from "node:process";
import { resolveRepoPath, validateManifestCompatibility } from "./azure-release-lib.mjs";
import { baseEvidence, parseStagingArgs, readJsonIfExists, writeStagingEvidence } from "./azure-staging-lib.mjs";

const { args, environment, execute } = parseStagingArgs();
const currentPath = args.current ? resolveRepoPath(String(args.current)) : null;
const targetPath = args.to ? resolveRepoPath(String(args.to)) : null;
const current = currentPath ? readJsonIfExists(currentPath) : null;
const target = targetPath ? readJsonIfExists(targetPath) : null;
const blockers = [];
if (!currentPath || !current) blockers.push("Current staging deployment manifest is not configured or readable.");
if (!targetPath || !target) blockers.push("Known-good target deployment manifest is not configured or readable.");
const compatibilityErrors = current && target ? validateManifestCompatibility(current, target) : [];

const report = {
  ...baseEvidence("rollback_drill", environment),
  mode: execute ? "execute" : "dry_run",
  source_release: current?.release_id ?? null,
  target_release: target?.release_id ?? null,
  affected_components: ["api revision", "web revision", "widget iframe/static current release", "SDK major alias"],
  compatibility_result: compatibilityErrors.length === 0 && blockers.length === 0 ? "compatible" : "blocked",
  compatibility_errors: compatibilityErrors,
  status: blockers.length === 0 && compatibilityErrors.length === 0 && execute ? "ready_for_live_rollback_drill" : "blocked_missing_prerequisites",
  blockers,
  health_result: "not_executed",
  smoke_result: "not_executed",
  restoration_result: "not_executed",
  overall_status: "not_executed",
};

if (report.status === "ready_for_live_rollback_drill") {
  report.status = "not_executed_by_repository_script";
  report.overall_status = "requires_operator_execution";
  report.note = "Execute rollback in the protected staging workflow/runbook after approving the compatible plan. No automatic DB downgrade is supported.";
}

writeStagingEvidence("rollback.json", report);
console.log(JSON.stringify(report, null, 2));
if (execute && report.status === "blocked_missing_prerequisites") process.exit(1);
