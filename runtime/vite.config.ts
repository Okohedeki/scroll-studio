import { defineConfig } from "vite";
import { resolve } from "node:path";

// Builds the browser runtime into the engine, where the site compiler copies it into every dist/.
export default defineConfig({
  // relative base: chunk preloads resolve next to index.js, wherever a site is hosted (not at the server root)
  base: "./",
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
        // NOTICE.md: this comment must stay in every copy of the runtime (the Output Exception depends on it)
        banner: "/*! Scroll Studio runtime by Edeki Okoh: https://github.com/Okohedeki/scroll-studio. GNU AGPL-3.0 with the Scroll Studio Output Exception (see NOTICE.md); keep this notice. */",
        entryFileNames: "index.js",
        chunkFileNames: "chunks/[name]-[hash].js",
        assetFileNames: (a) => (a.names?.[0]?.endsWith(".css") ? "studio.css" : "assets/[name]-[hash][extname]"),
      },
    },
  },
});
