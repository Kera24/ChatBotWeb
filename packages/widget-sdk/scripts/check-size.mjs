import { gzipSync } from "node:zlib";
import { readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const budgets = [
  { file: "index.js", gzipBytes: 10 * 1024 },
  { file: "yoranix-widget-sdk.global.js", gzipBytes: 12 * 1024 },
];

const dist = join(process.cwd(), "dist");
let failed = false;
for (const budget of budgets) {
  const path = join(dist, budget.file);
  const rawBytes = statSync(path).size;
  const gzipBytes = gzipSync(readFileSync(path)).byteLength;
  if (gzipBytes > budget.gzipBytes) {
    failed = true;
    console.error(`${budget.file} exceeds gzip budget: ${gzipBytes} > ${budget.gzipBytes}`);
  }
  process.stdout.write(`${budget.file}: raw=${rawBytes} gzip=${gzipBytes} budget=${budget.gzipBytes}\n`);
}

if (failed) {
  process.exit(1);
}