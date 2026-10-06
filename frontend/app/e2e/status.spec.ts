import { expect, test } from "@playwright/test";

test("shows every check as working when the API is ready", async ({ page }) => {
  await page.route("**/readyz", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ready", checks: { database: "ok", migrations: "ok", queue: "ok" } }),
    }),
  );
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "System status" })).toBeVisible();
  await expect(page.getByTestId("readiness-summary")).toHaveText("All systems are working.");
  await expect(page.getByText("Working", { exact: true })).toHaveCount(3);
  await expect(page.getByText(/not legal or tax advice/)).toBeVisible();
});

test("shows which part is down when the API is not ready", async ({ page }) => {
  await page.route("**/readyz", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ status: "not_ready", checks: { database: "ok", migrations: "ok", queue: "fail" } }),
    }),
  );
  await page.goto("/");
  await expect(page.getByTestId("readiness-summary")).toContainText("not working right now");
  await expect(page.getByText("Not working", { exact: true })).toHaveCount(1);
});

test("shows the request ID when the API fails", async ({ page }) => {
  await page.route("**/readyz", (route) =>
    route.fulfill({
      status: 500,
      contentType: "application/problem+json",
      headers: { "x-request-id": "req-e2e-12345678" },
      body: JSON.stringify({
        title: "Something went wrong",
        status: 500,
        code: "internal_error",
        detail: "Unexpected error. Quote the request ID if you contact support.",
        request_id: "req-e2e-12345678",
      }),
    }),
  );
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("req-e2e-12345678");
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
});

test("unknown pages show a way back", async ({ page }) => {
  await page.goto("/no-such-page");
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
});
