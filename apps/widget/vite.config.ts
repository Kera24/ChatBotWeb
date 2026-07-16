import { defineConfig } from "vitest/config";
import { resolve } from "node:path";

export default defineConfig({
  resolve: {
    alias: {
      "@yoranix/widget-sdk": resolve(__dirname, "../../packages/widget-sdk/src/index.ts"),
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    minify: "esbuild",
    sourcemap: false,
    target: "es2020",
    rollupOptions: {
      output: {
        entryFileNames: "assets/[name]-[hash].js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]",
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
});
