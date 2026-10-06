import { defineConfig, devices } from "@playwright/test";

// E2E runs the real stack on its own ports (clear of `make dev`): the API with a fresh database and the fake
// identity provider on :8001 (backend/tests/e2e_server.py; needs TEST_DATABASE_ADMIN_URL), and Vite on :5174
// proxying /v1 to it. Specs may still mock individual API responses with page.route().
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_PATH; // optional: a preinstalled Chromium
const API_PORT = 8001;
const APP_PORT = 5174;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: `http://localhost:${APP_PORT}`,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], ...(executablePath ? { launchOptions: { executablePath } } : {}) },
    },
  ],
  webServer: [
    {
      command: "uv run python -m tests.e2e_server",
      cwd: "../../backend",
      url: `http://localhost:${API_PORT}/healthz`,
      env: { E2E_API_PORT: String(API_PORT), E2E_APP_ORIGIN: `http://localhost:${APP_PORT}` },
      reuseExistingServer: false,
      timeout: 120_000,
      gracefulShutdown: { signal: "SIGTERM", timeout: 10_000 },
      stdout: "pipe",
    },
    {
      command: `pnpm exec vite --port ${APP_PORT} --strictPort`,
      url: `http://localhost:${APP_PORT}`,
      env: { VITE_DEV_API_TARGET: `http://localhost:${API_PORT}` },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
