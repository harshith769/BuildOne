import { defineConfig, devices } from "@playwright/test";

// E2E runs against the Vite dev server. Tests mock API responses with page.route() unless they say otherwise,
// so they need no backend. Full-stack flows (sign-in -> plan) arrive with M2 and M8.
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_PATH; // optional: a preinstalled Chromium

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], ...(executablePath ? { launchOptions: { executablePath } } : {}) },
    },
  ],
  webServer: {
    command: "pnpm dev",
    url: "http://localhost:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
