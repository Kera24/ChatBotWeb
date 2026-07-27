import assert from "node:assert/strict";
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { delimiter, join } from "node:path";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import test from "node:test";

const root = process.cwd();
const environmentDir = join(root, "infrastructure/azure/environments");

function run(args, options = {}) {
  return spawnSync(process.execPath, args, {
    cwd: root,
    encoding: "utf8",
    env: {
      ...process.env,
      AZURE_SUBSCRIPTION_ID: "",
      AZURE_POSTGRES_ADMIN_PASSWORD: "",
    },
    ...options,
  });
}

test("infra what-if skips safely when secure password is missing", () => {
  const result = run(["scripts/azure-infra-whatif.mjs", "staging"], {
    env: {
      ...process.env,
      AZURE_SUBSCRIPTION_ID: "sub-staging",
      AZURE_POSTGRES_ADMIN_PASSWORD: "",
    },
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.match(result.stdout, /credentials\/secure parameters are not configured/);
  assert.doesNotMatch(result.stdout, /postgresAdministratorPassword=/);
  assert.doesNotMatch(result.stdout, /\$AZURE_POSTGRES_ADMIN_PASSWORD/);
  assert.equal(findGeneratedParameterFiles().length, 0);
});

test("infra what-if creates a temporary bicepparam overlay and constructs safe Azure args", () => {
  const fake = createFakeAz("success");
  const secret = "what-if-password-never-log";
  const result = run(["scripts/azure-infra-whatif.mjs", "staging"], {
    env: fakeEnv(fake.binDir, {
      AZURE_SUBSCRIPTION_ID: "sub-staging",
      AZURE_POSTGRES_ADMIN_PASSWORD: secret,
      AZURE_LOCATION: "australiaeast",
    }),
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);

  const calls = readFakeAzCalls(fake.callsPath);
  const account = calls.find((call) => call.args.slice(0, 2).join(" ") === "account set");
  const whatIf = calls.find((call) => call.args.slice(0, 3).join(" ") === "deployment sub what-if");
  assert.ok(account, "expected az account set to run");
  assert.ok(whatIf, "expected az deployment sub what-if to run");
  assert.ok(!whatIf.args.includes("--template-file"));
  assert.ok(whatIf.args.includes("--parameters"));
  assert.ok(whatIf.parameterFile.endsWith(".generated.bicepparam"));
  assert.ok(whatIf.parameterContent.includes("using '../main.bicep'"));
  assert.ok(whatIf.parameterContent.includes("param postgresAdministratorPassword = readEnvironmentVariable('AZURE_POSTGRES_ADMIN_PASSWORD')"));
  assert.ok(whatIf.args.every((arg) => !arg.includes(secret)));
  assert.ok(whatIf.args.every((arg) => !arg.includes("$AZURE_POSTGRES_ADMIN_PASSWORD")));
  assert.doesNotMatch(result.stdout + result.stderr + JSON.stringify(calls), new RegExp(secret));
  assert.equal(existsSync(whatIf.parameterFile), false, "temporary bicepparam should be deleted");
  assert.equal(findGeneratedParameterFiles().length, 0);
});

test("infra what-if removes the temporary bicepparam when Azure CLI fails", () => {
  const fake = createFakeAz("what-if-fails");
  const secret = "failed-what-if-password-never-log";
  const result = run(["scripts/azure-infra-whatif.mjs", "staging"], {
    env: fakeEnv(fake.binDir, {
      AZURE_SUBSCRIPTION_ID: "sub-staging",
      AZURE_POSTGRES_ADMIN_PASSWORD: secret,
    }),
  });
  assert.notEqual(result.status, 0);
  const calls = readFakeAzCalls(fake.callsPath);
  const whatIf = calls.find((call) => call.args.slice(0, 3).join(" ") === "deployment sub what-if");
  assert.ok(whatIf, "expected what-if to run before failing");
  assert.equal(existsSync(whatIf.parameterFile), false, "temporary bicepparam should be deleted after failure");
  assert.equal(findGeneratedParameterFiles().length, 0);
  assert.doesNotMatch(result.stdout + result.stderr + JSON.stringify(calls), new RegExp(secret));
});

function createFakeAz(mode) {
  const dir = join(tmpdir(), `fake-az-infra-${process.pid}-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  const binDir = join(dir, "bin");
  mkdirSync(binDir, { recursive: true });
  const callsPath = join(dir, "calls.jsonl");
  const scriptPath = join(binDir, process.platform === "win32" ? "az.cmd" : "az");
  const nodeScript = join(dir, "fake-az.mjs");
  writeFileSync(
    nodeScript,
    `import { appendFileSync, readFileSync } from "node:fs";\n` +
      `const callsPath = ${JSON.stringify(callsPath)};\n` +
      `const mode = ${JSON.stringify(mode)};\n` +
      `const args = process.argv.slice(2);\n` +
      `let parameterFile = null;\n` +
      `let parameterContent = null;\n` +
      `for (let i = 0; i < args.length; i += 1) { if (args[i] === "--parameters") parameterFile = args[i + 1]; }\n` +
      `if (parameterFile && parameterFile.endsWith(".bicepparam")) parameterContent = readFileSync(parameterFile, "utf8");\n` +
      `appendFileSync(callsPath, JSON.stringify({ args, parameterFile, parameterContent }) + "\\n");\n` +
      `if (args.slice(0, 2).join(" ") === "account set") process.exit(0);\n` +
      `if (args.slice(0, 3).join(" ") === "deployment sub what-if") {\n` +
      `  if (mode === "success") { console.log("Resource changes: Create api"); process.exit(0); }\n` +
      `  console.error("Error BCP258: The following parameters are declared in the Bicep file but are missing values: postgresAdministratorPassword.");\n` +
      `  process.exit(1);\n` +
      `}\n` +
      `console.error("unexpected az args " + args.join(" "));\n` +
      `process.exit(2);\n`,
    "utf8",
  );
  if (process.platform === "win32") {
    writeFileSync(scriptPath, `@echo off\n"${process.execPath}" "${nodeScript}" %*\n`, "utf8");
  } else {
    writeFileSync(scriptPath, `#!/bin/sh\nexec "${process.execPath}" "${nodeScript}" "$@"\n`, { mode: 0o755 });
  }
  return { binDir, callsPath };
}

function fakeEnv(binDir, values) {
  return {
    ...process.env,
    ...values,
    PATH: `${binDir}${delimiter}${process.env.PATH}`,
  };
}

function readFakeAzCalls(callsPath) {
  return readFileSync(callsPath, "utf8")
    .trim()
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

function findGeneratedParameterFiles() {
  return readdirSync(environmentDir)
    .filter((name) => name.endsWith(".generated.bicepparam"))
    .map((name) => join(environmentDir, name));
}