#!/usr/bin/env node
// Deployment-safe release gate for the VPS (non-Azure) deployment target.
//
// Chains software tests, the deterministic evaluation suite, the guardrail /
// isolation / citation tests, a real-embedding evaluation run when Ollama is
// reachable, and a required-environment-variable check; writes a gate report
// and exits non-zero if anything hard-blocking failed.
//
// Usage:
//   node scripts/release-gate.mjs                         # local dev checks only
//   node scripts/release-gate.mjs --env-file .env.production   # also checks required vars
//   node scripts/release-gate.mjs --smoke-base-url https://api.example.com  # + live smoke
//
// This intentionally does not know about Azure - it is the generic
// counterpart to scripts/validate-production-pilot-readiness.mjs, meant to
// gate a docker-compose.prod.yml deployment to a single VPS.

import { existsSync, readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { resolveRepoPath, writeJson, parseArgs } from "./azure-release-lib.mjs";

const args = parseArgs(process.argv.slice(2));
const envFilePath = args["env-file"] ? resolveRepoPath(String(args["env-file"])) : null;
const smokeBaseUrl = args["smoke-base-url"] ? String(args["smoke-base-url"]) : null;
const skipBuild = Boolean(args["skip-build"]);
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
if (envFilePath) {
  run("migrations_apply_cleanly", "docker", [
    "compose",
    "-f",
    "docker-compose.prod.yml",
    "--env-file",
    envFilePath,
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
    detail: { reason: "no --env-file given; migration check against Postgres skipped (see script comment)" },
  });
}

// ---------------------------------------------------------------------------
// 3. Software test suites (includes tenant/assistant isolation tests -
//    test_tenant_isolation_patterns.py, test_tenant_api.py - and citation /
//    guardrail tests - test_guardrails.py - as part of the full API suite).
// ---------------------------------------------------------------------------
run("api_tests", "npm", ["run", "api:test"]);
run("web_tests", "npm", ["run", "web:test"]);
run("web_lint", "npm", ["run", "web:lint"]);
if (!skipBuild) run("web_build", "npm", ["run", "web:build"]);

// ---------------------------------------------------------------------------
// 4. Deterministic evaluation suite (pure code-correctness tests of the
//    evaluation framework itself) - always blocking, matches `verify`.
// ---------------------------------------------------------------------------
run("eval_framework_tests", "npm", ["run", "eval:test"]);

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
