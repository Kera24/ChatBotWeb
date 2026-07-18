import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const dist = fileURLToPath(new URL("../dist", import.meta.url));
const assets = join(dist, "assets");
if (!existsSync(assets)) throw new Error("Widget production assets are missing. Run npm run build first.");

const forbidden = [
  { value: "__yoranixWidgetTestHarness", reason: "test harness global" },
  { value: "VITE_WIDGET_TEST_API_HOST", reason: "test API env key" },
  { value: "127.0.0.1:4300", reason: "local mock API host" },
  { value: "127.0.0.1:4100", reason: "local host fixture" },
  { value: "pss_dev_abcdefghijklmnop", reason: "session token fixture" },
  { value: "Hello from browser test", reason: "browser test message" },
  { value: "Token isolation check", reason: "security test message" },
  { value: "mock public API", reason: "mock server content" },
];

const jsFiles = readdirSync(assets).filter((name) => name.endsWith(".js"));
if (jsFiles.length === 0) throw new Error("No production JavaScript assets found.");

for (const fileName of jsFiles) {
  const fullPath = join(assets, fileName);
  const text = readFileSync(fullPath, "utf8");
  for (const item of forbidden) {
    if (text.includes(item.value)) {
      throw new Error(`${fileName} contains forbidden ${item.reason}: ${item.value}`);
    }
  }
  if (/console\.(log|debug|info)\(/.test(text)) {
    throw new Error(`${fileName} contains production console output`);
  }
}

for (const fileName of readdirSync(dist)) {
  const fullPath = join(dist, fileName);
  if (statSync(fullPath).isFile() && fileName.endsWith(".map")) {
    throw new Error(`Unexpected production source map: ${fileName}`);
  }
}

console.log(`Production widget inspection passed for ${jsFiles.length} JavaScript asset(s).`);
