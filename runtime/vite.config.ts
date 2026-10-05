import { defineConfig } from "vite";
import { resolve } from "node:path";

// Builds the browser runtime into the engine, where the site compiler copies it into every dist/.
export default defineConfig({
  build: {
    outDir: resolve(__dirname, "../engine/compile/static/runtime"),
    emptyOutDir: true,
    target: "es2022",
    cssCodeSplit: false,
    sourcemap: false,
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      input: { index: resolve(__dirname, "src/index.ts") },
      output: {
        format: "es",
        entryFileNames: "index.js",
        chunkFileNames: "chunks/[name]-[hash].js",
        assetFileNames: (a) => (a.names?.[0]?.endsWith(".css") ? "studio.css" : "assets/[name]-[hash][extname]"),
      },
    },
  },
});
