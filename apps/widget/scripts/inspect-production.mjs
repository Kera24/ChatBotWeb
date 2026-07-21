import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const dist = fileURLToPath(new URL("../dist", import.meta.url));
const assets = join(dist, "assets");
const releaseArtifacts = fileURLToPath(new URL("../../../artifacts/widget-release", import.meta.url));
if (!existsSync(assets)) throw new Error("Widget production assets are missing. Run npm run build first.");

const forbidden = [
  { value: "__yoranixWidgetTestHarness", reason: "test harness global" },
  { value: "VITE_WIDGET_TEST_API_HOST", reason: "test API env key" },
  { value: "127.0.0.1:4300", reason: "local mock API host" },
  { value: "127.0.0.1:4100", reason: "local host fixture" },
  { value: "127.0.0.1:4200", reason: "local widget fixture" },
  { value: "pss_dev_abcdefghijklmnop", reason: "session token fixture" },
  { value: "Hello from browser test", reason: "browser test message" },
  { value: "Token isolation check", reason: "security test message" },
  { value: "mock public API", reason: "mock server content" },
  { value: "Alpha Observatory", reason: "synthetic real-backend fixture content" },
  { value: "Beta Archive", reason: "synthetic real-backend fixture content" },
  { value: "WIDGET_REAL_BACKEND_TEST", reason: "real-backend test environment flag" },
  { value: "synthetic-widget-b2", reason: "synthetic real-backend fixture marker" },
  { value: "widget-pilot-verification", reason: "pilot verification artifact name" },
  { value: "widget-pilot-readiness", reason: "pilot readiness artifact name" },
  { value: "PUBLIC_WIDGETS_ENABLED", reason: "public widget kill-switch config" },
  { value: "PUBLIC_WIDGET_PILOT_ALLOWLIST", reason: "pilot allowlist server config" },
];

const jsFiles = readdirSync(assets).filter((name) => name.endsWith(".js"));
if (jsFiles.length === 0) throw new Error("No production JavaScript assets found.");

for (const fileName of jsFiles) {
  inspectTextFile(join(assets, fileName), fileName);
}

for (const fileName of readdirSync(dist)) {
  const fullPath = join(dist, fileName);
  if (statSync(fullPath).isFile() && fileName.endsWith(".map")) {
    throw new Error(`Unexpected production source map: ${fileName}`);
  }
}

if (existsSync(releaseArtifacts)) {
  const inspected = inspectDirectory(releaseArtifacts);
  console.log(`Production release artifact inspection passed for ${inspected} file(s).`);
}

console.log(`Production widget inspection passed for ${jsFiles.length} JavaScript asset(s).`);

function inspectDirectory(root) {
  let inspected = 0;
  for (const fileName of readdirSync(root)) {
    const fullPath = join(root, fileName);
    const stat = statSync(fullPath);
    if (stat.isDirectory()) {
      inspected += inspectDirectory(fullPath);
      continue;
    }
    if (!/\.(js|html|json|css)$/.test(fileName)) continue;
    inspectTextFile(fullPath, fileName);
    inspected += 1;
  }
  return inspected;
}

function inspectTextFile(fullPath, label) {
  const text = readFileSync(fullPath, "utf8");
  for (const item of forbidden) {
    if (text.includes(item.value)) {
      throw new Error(`${label} contains forbidden ${item.reason}: ${item.value}`);
    }
  }
  if (label !== "loader.js" && /console\.(log|debug|info)\(/.test(text)) {
    throw new Error(`${label} contains production console output`);
  }
}
