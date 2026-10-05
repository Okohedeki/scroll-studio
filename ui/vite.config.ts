import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `npm run dev:ui` proxies the API to a running `studio ui` (port 5180).
export default defineConfig({
  plugins: [react()],
  server: { port: 5181, proxy: { "/api": "http://127.0.0.1:5180", "/preview": "http://127.0.0.1:5180", "/files": "http://127.0.0.1:5180" } },
  build: { outDir: "dist", emptyOutDir: true },
});
