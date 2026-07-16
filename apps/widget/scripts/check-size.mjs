import { readFileSync, readdirSync, statSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../dist/assets", import.meta.url));
const budgets = { js: 30 * 1024, css: 10 * 1024 };
let found = false;
for (const fileName of readdirSync(root)) {
  if (!fileName.endsWith(".js") && !fileName.endsWith(".css")) continue;
  found = true;
  const fullPath = join(root, fileName);
  const raw = statSync(fullPath).size;
  const gzip = gzipSync(readFileSync(fullPath)).length;
  const kind = fileName.endsWith(".js") ? "js" : "css";
  const budget = budgets[kind];
  console.log(`${fileName}: raw=${raw} gzip=${gzip} budget=${budget}`);
  if (gzip > budget) {
    throw new Error(`${fileName} exceeds ${kind} gzip budget`);
  }
}
if (!found) throw new Error("No widget app assets found");
