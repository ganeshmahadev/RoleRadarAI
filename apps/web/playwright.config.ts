import { defineConfig, devices } from "@playwright/test";

/**
 * E2E runs an isolated stack so tests never modify the development database:
 * - API on :8100 backed by `roleradar_e2e` (rebuilt + SIRI seed imported each run)
 * - web on :3100 pointing at that API
 * Requires `docker compose up -d postgres redis`.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  use: {
    baseURL: "http://localhost:3100",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "./tests/e2e/start-api.sh",
      url: "http://localhost:8100/api/v1/health",
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: "pipe",
    },
    {
      command: "pnpm exec next dev --port 3100",
      url: "http://localhost:3100",
      reuseExistingServer: false,
      timeout: 120_000,
      env: { NEXT_PUBLIC_API_BASE_URL: "http://localhost:8100" },
    },
  ],
});
