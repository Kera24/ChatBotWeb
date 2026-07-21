import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const repoRoot = fileURLToPath(new URL("../../..", import.meta.url));
const alertPolicy = new URL("../../../deployment/widget/alerts.json", import.meta.url);

const booleans = [
  "PUBLIC_WIDGETS_ENABLED",
  "PUBLIC_WIDGET_MESSAGES_ENABLED",
  "PUBLIC_WIDGET_PILOT_ENFORCEMENT_ENABLED",
];

for (const name of booleans) {
  const value = process.env[name];
  if (value === undefined || value === "") continue;
  if (!/^(1|0|true|false|yes|no|on|off)$/i.test(value)) {
    throw new Error(`${name} must be a strict boolean value.`);
  }
}

for (const name of ["PUBLIC_WIDGET_PILOT_ALLOWLIST", "PUBLIC_WIDGET_DISABLED_WIDGETS"]) {
  const value = process.env[name] ?? "";
  const items = value.split(",").map((item) => item.trim()).filter(Boolean);
  if (new Set(items).size !== items.length) throw new Error(`${name} contains duplicate identifiers.`);
  for (const item of items) {
    if (item.length > 160 || /\s/.test(item)) throw new Error(`${name} contains an invalid identifier.`);
  }
}

const policy = JSON.parse(readFileSync(alertPolicy, "utf8"));
if (!Array.isArray(policy.alerts) || policy.alerts.length === 0) {
  throw new Error("deployment/widget/alerts.json must contain alerts.");
}
for (const alert of policy.alerts) {
  for (const field of ["alert_id", "severity", "signal", "threshold", "evaluation_window", "consecutive_failures", "runbook"]) {
    if (!alert[field]) throw new Error(`Alert ${alert.alert_id ?? "(unknown)"} is missing ${field}.`);
  }
  if (!["warning", "incident", "critical"].includes(alert.severity)) throw new Error(`Alert ${alert.alert_id} has invalid severity.`);
}

console.log(`Widget operational configuration valid for ${repoRoot}`);

