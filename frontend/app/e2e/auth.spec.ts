import { expect, test, type Page } from "@playwright/test";

// Full stack: Vite -> API (:8001) -> fake identity provider -> real Postgres. No mocks.

function uniqueEmail(label: string): string {
  return `e2e-${label}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.test`;
}

async function signInWithFakeIdp(page: Page, email: string, name: string) {
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("heading", { name: "Fake sign-in" })).toBeVisible();
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByRole("button", { name: "Sign in" }).click();
}

test("a new user signs up, stays signed in, signs out, and signs back in", async ({ page }) => {
  const email = uniqueEmail("signup");

  await page.goto("/");
  await expect(page).toHaveURL(/\/sign-in\?return_to=%2F/);
  await expect(page.getByRole("heading", { name: "Sign in to BuildOne" })).toBeVisible();

  await signInWithFakeIdp(page, email, "Asha E2E");

  // S2: nothing is created until 18+ and the terms are accepted.
  await expect(page.getByRole("heading", { name: "Welcome to BuildOne" })).toBeVisible();
  await expect(page.getByText(email)).toBeVisible();
  const create = page.getByRole("button", { name: "Create my account" });
  await expect(create).toBeDisabled();
  await page.getByLabel("I am 18 years old or older.").check();
  await expect(create).toBeDisabled();
  await page.getByLabel(/I accept the terms of use/).check();
  await create.click();

  await expect(page.getByRole("heading", { name: "Welcome, Asha E2E" })).toBeVisible();
  await expect(page.getByTestId("me-email")).toHaveText(email);
  await expect(page.getByText(/not legal or tax advice/)).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { name: "Welcome, Asha E2E" })).toBeVisible();

  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByText("You're signed out.")).toBeVisible();
  await page.goto("/");
  await expect(page).toHaveURL(/\/sign-in/);

  // Returning user: straight back in, no consent screen.
  await signInWithFakeIdp(page, email, "Asha E2E");
  await expect(page.getByRole("heading", { name: "Welcome, Asha E2E" })).toBeVisible();
});

test("an under-18 visitor is turned away and nothing is saved", async ({ page }) => {
  const email = uniqueEmail("minor");

  await page.goto("/sign-in");
  await signInWithFakeIdp(page, email, "Young Visitor");
  await expect(page.getByRole("heading", { name: "Welcome to BuildOne" })).toBeVisible();
  await page.getByRole("button", { name: "I'm under 18" }).click();
  await expect(page.getByText(/only for people aged 18 or older/)).toBeVisible();

  // No account was created: signing in again with the same email asks again.
  await signInWithFakeIdp(page, email, "Young Visitor");
  await expect(page.getByRole("heading", { name: "Welcome to BuildOne" })).toBeVisible();
});

test("sign-in errors from the callback are explained", async ({ page }) => {
  await page.goto("/sign-in?error=sign_in_expired");
  await expect(page.getByRole("alert")).toHaveText(/timed out/);
});
