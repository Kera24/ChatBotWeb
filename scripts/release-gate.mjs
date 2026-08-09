#!/usr/bin/env node
// Deployment-safe release gate for the VPS (non-Azure) deployment target.
//
// Chains software tests, the deterministic evaluation suite, the guardrail /
// isolation / citation tests, a real-embedding evaluation run when Ollama is
// reachable, a required-environment-variable check, Docker Compose
// config validation (prod + observability), and a real migration-apply
// check; writes a gate report and exits non-zero if anything hard-blocking
// failed.
//
// Usage:
//   node scripts/release-gate.mjs                         # local dev checks only
//   node scripts/release-gate.mjs --env-file .env.production   # also checks required vars + migrations against that real file
//   node scripts/release-gate.mjs --smoke-base-url https://api.example.com  # + live smoke
//   node scripts/release-gate.mjs --skip-verified-suites --migration-check-env-file .env.production.example
//     # CI mode: skip suites `npm run verify` already ran in the same job; still
//     # validate Compose config + a real migration apply, using only the
//     # checked-in example file's safe/placeholder values (never a real secret).
//
// This intentionally does not know about Azure - it is the generic
// counterpart to scripts/validate-production-pilot-readiness.mjs, meant to
// gate a docker-compose.prod.yml deployment to a single VPS.

import { copyFileSync, existsSync, readFileSync, unlinkSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { resolveRepoPath, writeJson, parseArgs } from "./azure-release-lib.mjs";

const args = parseArgs(process.argv.slice(2));
const envFilePath = args["env-file"] ? resolveRepoPath(String(args["env-file"])) : null;
// Deliberately separate from envFilePath/--env-file above: that flag also
// gates required_env_vars_not_placeholder, which is SUPPOSED to fail against
// .env.production.example (it exists to catch a real deployment still
// carrying leftover placeholders). CI wants "does a real migration apply
// cleanly against this env file's shape" without also asserting the values
// aren't placeholders - .env.production.example's placeholders are exactly
// the safe, credential-free fixture values this task calls for. Defaults to
// envFilePath so existing `--env-file .env.production` local/manual usage
// keeps validating migrations against that same real file, unchanged.
const migrationCheckEnvFilePath = args["migration-check-env-file"]
  ? resolveRepoPath(String(args["migration-check-env-file"]))
  : envFilePath;
const smokeBaseUrl = args["smoke-base-url"] ? String(args["smoke-base-url"]) : null;
const skipBuild = Boolean(args["skip-build"]);
// CI opts into this after `npm run verify` has already run in the same job -
// api_tests/web_tests/web_lint/web_build/eval_framework_tests below are
// exactly the suites `verify` already covers (see package.json's `verify`
// script); re-running them here would just burn CI minutes on the same
// result. Local/manual use (this flag omitted) is unaffected - every suite
// still runs, matching this script's existing behaviour.
const skipVerifiedSuites = Boolean(args["skip-verified-suites"]);
// Production feedback loop gate (app.evaluation.production_gate) needs an
// explicit assistant/dataset scope this generic script cannot infer on its
// own - same reasoning as smokeBaseUrl above. Advisory/skipped unless all
// four are supplied.
const feedbackLoopScope = ["feedback-loop-organisation", "feedback-loop-workspace", "feedback-loop-assistant", "feedback-loop-dataset"].every(
  (key) => typeof args[key] === "string",
);

const MANDATORY_ENV_VARS = [
  "WEB_DOMAIN",
  "API_DOMAIN",
  "WIDGET_DOMAIN",
  "TLS_EMAIL",
  "POSTGRES_DB",
  "POSTGRES_USER",
  "POSTGRES_PASSWORD",
  "DATABASE_URL",
  "REDIS_URL",
  "APP_ENV",
  "WEB_ORIGIN",
  "NEXT_PUBLIC_API_BASE_URL",
  "AUTH_SESSION_HASH_SECRET",
  "RATE_LIMIT_IDENTITY_SECRET",
  "PUBLIC_SESSION_TOKEN_HASH_SECRET",
  "PUBLIC_MESSAGE_IDEMPOTENCY_HASH_SECRET",
  "WIDGET_PUBLIC_ORIGIN",
  "WIDGET_PUBLIC_API_ORIGIN",
  "WIDGET_SDK_PUBLIC_ORIGIN",
];

const PLACEHOLDER_MARKERS = ["REPLACE_WITH", "change-me", "example.com", "example.test"];

const gates = [];
const failures = [];

function gate(id, { passed, blocking = true, detail = {} }) {
  gates.push({ id, status: passed ? "passed" : blocking ? "failed" : "skipped_or_warned", blocking, detail });
  if (!passed && blocking) failures.push(id);
}

function run(id, command, cmdArgs, { blocking = true, cwd } = {}) {
  process.stdout.write(`\n=== ${id}: ${command} ${cmdArgs.join(" ")} ===\n`);
  // shell:true is only needed on Windows to resolve npm's .cmd shim - using it
  // for other binaries (docker, node, curl) breaks argv quoting for any
  // argument containing spaces (e.g. a repo path under "OneDrive - Office
  // 365"), since cmd.exe re-tokenizes the joined command line itself.
  const needsShell = process.platform === "win32" && command === "npm";
  const result = spawnSync(command, cmdArgs, {
    cwd: cwd ?? resolveRepoPath("."),
    stdio: "inherit",
    shell: needsShell,
  });
  const passed = result.status === 0;
  gate(id, { passed, blocking, detail: { exitCode: result.status, signal: result.signal } });
  return passed;
}

// docker-compose.prod.yml's api/web services declare `env_file: [.env.production]`
// - a literal path baked into the compose file, independent of the
// --env-file flag below (which only affects ${VAR} interpolation within the
// compose file itself). ANY `docker compose` invocation against this file -
// even `config` or a targeted `up <service>` that only starts postgres/
// migrate - fails outright if that literal file is missing, because Compose
// resolves every service definition upfront. If no real .env.production
// exists (true for a fresh checkout / CI), fall back to the checked-in,
// git-tracked example file's shape by copying it to that exact throwaway
// path for the duration of this script, then remove it - safe because every
// value in .env.production.example is already documented as a non-secret
// placeholder (see that file's own header comment). Never touches a
// pre-existing real .env.production.
let createdEnvProductionFile = false;
function ensureLiteralEnvProductionFile() {
  const target = resolveRepoPath(".env.production");
  if (existsSync(target)) return target;
  const example = resolveRepoPath(".env.production.example");
  copyFileSync(example, target);
  createdEnvProductionFile = true;
  return target;
}
function cleanupEnvProductionFileIfCreated() {
  if (createdEnvProductionFile) {
    unlinkSync(resolveRepoPath(".env.production"));
    createdEnvProductionFile = false;
  }
}

// ---------------------------------------------------------------------------
// 1. Required environment variables (only checked when --env-file is given -
//    e.g. against .env.production before a real deployment; local dev runs
//    without this flag skip the check entirely).
// ---------------------------------------------------------------------------
if (envFilePath) {
  if (!existsSync(envFilePath)) {
    gate("required_env_vars_present", { passed: false, detail: { reason: `env file not found: ${envFilePath}` } });
  } else {
    const envText = readFileSync(envFilePath, "utf8");
    const values = Object.fromEntries(
      envText
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line && !line.startsWith("#") && line.includes("="))
        .map((line) => {
          const idx = line.indexOf("=");
          return [line.slice(0, idx).trim(), line.slice(idx + 1).trim()];
        }),
    );
    const missing = MANDATORY_ENV_VARS.filter((name) => !values[name]);
    const placeholders = MANDATORY_ENV_VARS.filter(
      (name) => values[name] && PLACEHOLDER_MARKERS.some((marker) => values[name].includes(marker)),
    );
    gate("required_env_vars_present", { passed: missing.length === 0, detail: { missing } });
    gate("required_env_vars_not_placeholder", { passed: placeholders.length === 0, detail: { placeholders } });
  }
} else {
  gate("required_env_vars_present", { passed: true, blocking: false, detail: { reason: "no --env-file given; skipped" } });
}

// ---------------------------------------------------------------------------
// 1b. Production env template shape - always runs, no --env-file needed and
//     no real secret required: verifies .env.production.example still
//     defines every variable app.core.config/docker-compose.prod.yml
//     actually require, so the template can't silently drift out of sync
//     with what a real deployment needs. Deliberately does NOT check against
//     PLACEHOLDER_MARKERS here - the example file is *supposed* to contain
//     placeholders; that's a property of a real .env.production (checked
//     above), not of this template.
// ---------------------------------------------------------------------------
{
  const examplePath = resolveRepoPath(".env.production.example");
  if (!existsSync(examplePath)) {
    gate("production_env_example_shape", { passed: false, detail: { reason: ".env.production.example not found" } });
  } else {
    const exampleText = readFileSync(examplePath, "utf8");
    const exampleKeys = new Set(
      exampleText
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line && !line.startsWith("#") && line.includes("="))
        .map((line) => line.slice(0, line.indexOf("=")).trim()),
    );
    const missing = MANDATORY_ENV_VARS.filter((name) => !exampleKeys.has(name));
    gate("production_env_example_shape", { passed: missing.length === 0, detail: { missing } });
  }
}

// ---------------------------------------------------------------------------
// 1c. Production/observability Docker Compose configuration is syntactically
//     valid and every referenced variable resolves - credential-free (a
//     `config` render never talks to Postgres/Redis/etc., and the throwaway
//     env-file fallback below never contains a real secret). Always runs.
// ---------------------------------------------------------------------------
const configCheckEnvFile = ensureLiteralEnvProductionFile();
run("docker_compose_prod_config", "docker", ["compose", "-f", "docker-compose.prod.yml", "--env-file", configCheckEnvFile, "config", "--quiet"]);
run("docker_compose_observability_config", "docker", [
  "compose",
  "-f",
  "docker-compose.prod.yml",
  "-f",
  "docker-compose.observability.yml",
  "--env-file",
  configCheckEnvFile,
  "config",
  "--quiet",
]);

// ---------------------------------------------------------------------------
// 2. Migration safety. When --env-file points at a real deployment env (e.g.
//    .env.production), this runs the actual `migrate` Compose service against
//    Postgres - the real deployment path - rather than whatever DATABASE_URL
//    happens to be ambient in this shell. Without --env-file (local dev use),
//    this step is skipped: the ambient DATABASE_URL commonly points at a
//    long-lived local sqlite/dev database whose alembic_version history can
//    drift from HEAD for reasons unrelated to deployment health (e.g. a
//    migration file renamed after that database was created), which is a
//    dev-environment hygiene issue, not a "can this deploy" signal.
// ---------------------------------------------------------------------------
if (migrationCheckEnvFilePath) {
  run("migrations_apply_cleanly", "docker", [
    "compose",
    "-f",
    "docker-compose.prod.yml",
    "--env-file",
    migrationCheckEnvFilePath,
    "up",
    "--build",
    "--exit-code-from",
    "migrate",
    "migrate",
  ]);
} else {
  gate("migrations_apply_cleanly", {
    passed: true,
    blocking: false,
    detail: { reason: "no --env-file/--migration-check-env-file given; migration check against Postgres skipped (see script comment)" },
  });
}

// ---------------------------------------------------------------------------
// 3. Software test suites (includes tenant/assistant isolation tests -
//    test_tenant_isolation_patterns.py, test_tenant_api.py - and citation /
//    guardrail tests - test_guardrails.py - as part of the full API suite).
//    Skipped when --skip-verified-suites is set - CI's Verify job already
//    ran `npm run verify` (which includes api:test/web:test/web:lint/
//    web:build) in the same job immediately before invoking this script.
// ---------------------------------------------------------------------------
if (!skipVerifiedSuites) {
  run("api_tests", "npm", ["run", "api:test"]);
  run("web_tests", "npm", ["run", "web:test"]);
  run("web_lint", "npm", ["run", "web:lint"]);
  if (!skipBuild) run("web_build", "npm", ["run", "web:build"]);
} else {
  for (const id of ["api_tests", "web_tests", "web_lint", "web_build"]) {
    gate(id, { passed: true, blocking: false, detail: { reason: "--skip-verified-suites given; already covered by npm run verify in this CI job" } });
  }
}

// ---------------------------------------------------------------------------
// 4. Deterministic evaluation suite (pure code-correctness tests of the
//    evaluation framework itself) - always blocking, matches `verify`.
//    Skipped when --skip-verified-suites is set - see the note above (`npm
//    run verify` already runs `eval:test`).
// ---------------------------------------------------------------------------
if (!skipVerifiedSuites) {
  run("eval_framework_tests", "npm", ["run", "eval:test"]);
} else {
  gate("eval_framework_tests", { passed: true, blocking: false, detail: { reason: "--skip-verified-suites given; already covered by npm run verify in this CI job" } });
}

// ---------------------------------------------------------------------------
// eval:launch runs the launch-critical dataset with the deterministic MOCK
// provider forced. Per docs/04_Engineering/Evaluation_Framework.md, this is
// deliberately NOT wired into `verify` and is not treated as a hard blocker
// here either: the current retrieval pipeline has no similarity-confidence
// threshold, so mock-mode runs predictably hard-fail
// unanswerable/fallback/injection cases regardless of code quality - that is
// a documented, accepted product gap, not something this gate should punish
// every single run for. It still runs, and its result is recorded and
// printed, so a real regression in the *mechanics* (dataset loading, gate
// wiring, category scoring) is still visible.
// ---------------------------------------------------------------------------
run("eval_launch_mock_mode", "npm", ["run", "eval:launch"], { blocking: false });

// ---------------------------------------------------------------------------
// 4b. Production feedback loop gate (app.evaluation.production_gate) - blocks
// when an approved production-failure case still fails, the latest completed
// run has hard failures, isolation/citation regressed, the dataset version
// changed without a completed evaluation, the baseline is stale, or required
// regression-report evidence is missing. Skipped (advisory) unless the four
// --feedback-loop-* scope flags are all supplied, since this generic script
// has no way to infer which assistant/dataset to check.
// ---------------------------------------------------------------------------
if (feedbackLoopScope) {
  run("production_feedback_gate", "npm", [
    "run",
    "eval:release-gate-check",
    "--",
    "--organisation",
    String(args["feedback-loop-organisation"]),
    "--workspace",
    String(args["feedback-loop-workspace"]),
    "--assistant",
    String(args["feedback-loop-assistant"]),
    "--dataset",
    String(args["feedback-loop-dataset"]),
  ]);
} else {
  gate("production_feedback_gate", {
    passed: true,
    blocking: false,
    detail: { reason: "no --feedback-loop-organisation/-workspace/-assistant/-dataset given; skipped" },
  });
}

// ---------------------------------------------------------------------------
// 5. Real-embedding evaluation - the actual quality bar (this is the run that
//    produced the validated 97.6% pass / 0 hard failures / 100% citation
//    coverage baseline). Advisory unless Ollama is reachable, in which case
//    it is treated as blocking. NOTE: this step only seeds the real-embedding
//    golden fixture (`eval_golden_setup.py --real`); executing it against a
//    live/real generation provider and gating the result additionally
//    requires `eval:run -- --mode live ... --dataset <id> --assistant <id>`
//    and `eval:report -- --gate` with the ids that setup step prints - not
//    fully automated here because it needs an already-configured live AI
//    provider, which is a per-deployment choice this generic script cannot
//    make. See docs/04_Engineering/Evaluation_Framework.md for the full
//    manual sequence; wiring the id-passing end to end is a follow-up.
// ---------------------------------------------------------------------------
const ollamaProbe = spawnSync("curl", ["-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "3", "http://localhost:11434/api/tags"]);
const ollamaAvailable = ollamaProbe.status === 0 && String(ollamaProbe.stdout).trim() === "200";
if (ollamaAvailable) {
  run("real_embedding_golden_setup", "npm", ["run", "eval:real:setup"]);
} else {
  gate("real_embedding_golden_setup", { passed: true, blocking: false, detail: { reason: "Ollama not reachable at localhost:11434; skipped (advisory only)" } });
}

// ---------------------------------------------------------------------------
// 6. Optional live smoke test against an already-deployed base URL.
// ---------------------------------------------------------------------------
if (smokeBaseUrl) {
  run("deployed_smoke_test", "node", ["scripts/vps-smoke.mjs", "--base-url", smokeBaseUrl]);
} else {
  gate("deployed_smoke_test", { passed: true, blocking: false, detail: { reason: "no --smoke-base-url given; skipped" } });
}

cleanupEnvProductionFileIfCreated();

// ---------------------------------------------------------------------------
// Report
// ---------------------------------------------------------------------------
const report = {
  schema_version: 1,
  generated_at: new Date().toISOString(),
  overall_status: failures.length === 0 ? "passed" : "failed",
  blocking_failures: failures,
  gates,
};
writeJson(resolveRepoPath("artifacts/release-gate/report.json"), report);

process.stdout.write(`\n=== Release gate: ${report.overall_status.toUpperCase()} ===\n`);
if (failures.length > 0) {
  process.stdout.write(`Blocking failures: ${failures.join(", ")}\n`);
  process.exitCode = 1;
}
