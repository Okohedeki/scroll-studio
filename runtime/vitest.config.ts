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
      // every source file counts, tested or not, so the numbers are what the runtime really has covered; the GPU players and
      // the styles' painting code cannot run in jsdom and are the bulk of what is not
      reporter: ["text-summary", ["text", { skipFull: true }], "json-summary"],
      reportsDirectory: "coverage",
      // floors that only go up: when a change lifts a number, raise its floor in the same pull request
      thresholds: {
        lines: 18, statements: 18, functions: 29, branches: 74,
        "src/lib/**": { lines: 94, functions: 95, branches: 85 },
        "src/index.ts": { lines: 95, branches: 84 },
      },
    },
  },
});
