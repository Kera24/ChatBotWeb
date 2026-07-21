import { existsSync, readFileSync } from "node:fs";
import { isAbsolute, join } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = fileURLToPath(new URL("../../..", import.meta.url));
const args = process.argv.slice(2);
const currentIndex = args.indexOf("--current");
const targetIndex = args.indexOf("--to");
const currentPath = currentIndex !== -1 ? args[currentIndex + 1] : args[0];
const targetPath = targetIndex !== -1 ? args[targetIndex + 1] : args[1];
if (!currentPath || !targetPath) {
  throw new Error("Usage: npm run widget:rollback:plan -- <current-manifest> <target-manifest>");
}
const current = JSON.parse(readFileSync(resolveInput(currentPath), "utf8"));
const target = JSON.parse(readFileSync(resolveInput(targetPath), "utf8"));
if (current.protocol_major !== target.protocol_major) throw new Error("Incompatible protocol_major.");
if (current.api_version !== target.api_version) throw new Error("Incompatible api_version.");
console.log(JSON.stringify({
  schema_version: "1.0",
  mode: "dry_run",
  from_sdk_version: current.sdk_version,
  to_sdk_version: target.sdk_version,
  major_alias_path: target.major_alias_path,
  immutable_loader_path: target.immutable_loader_path,
  target_commit: target.build_commit,
  required_verification: [
    "npm run widget:release:build",
    "npm run widget:pilot:verify",
    "npm run widget:pilot:readiness",
    "post-deploy real smoke in target environment"
  ]
}, null, 2));


function resolveInput(value) {
  if (isAbsolute(value) || existsSync(value)) return value;
  return join(repoRoot, value);
}
