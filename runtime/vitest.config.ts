import { defineConfig } from "vitest/config";

// Unit tests for the browser runtime's logic, run in jsdom (no browser, no GPU). The build config stays in vite.config.ts so
// that nothing here can change the bundle. `npm test -w runtime` runs them with a v8 coverage report.
export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["test/**/*.test.ts"],
    setupFiles: ["test/setup.ts"],
    restoreMocks: true,
    css: false,
    coverage: {
      provider: "v8",
      include: ["src/**/*.ts"],
      reporter: ["text-summary", "text", "json-summary"],
      reportsDirectory: "coverage",
    },
  },
});
