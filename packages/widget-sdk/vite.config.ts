import { defineConfig } from "vitest/config";

export default defineConfig({
  build: {
    lib: {
      entry: "src/index.ts",
      name: "YoranixWidgetSDK",
      formats: ["es", "iife"],
      fileName: (format) => (format === "es" ? "index.js" : "yoranix-widget-sdk.global.js"),
    },
    emptyOutDir: true,
    minify: "esbuild",
    sourcemap: true,
    target: "es2020",
    rollupOptions: {
      output: {
        exports: "named",
      },
    },
  },
  test: {
    environment: "node",
    globals: true,
  },
});