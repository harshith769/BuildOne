import { expect, type Page } from "@playwright/test";

export function uniqueEmail(label: string): string {
  return `e2e-${label}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
}

/** From the sign-in screen through the fake identity provider's form. */
export async function signInWithFakeIdp(page: Page, email: string, name: string) {
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("heading", { name: "Fake sign-in" })).toBeVisible();
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByRole("button", { name: "Sign in" }).click();
}

/** New user on the welcome screen: confirm 18+, accept the terms, create the account. */
export async function completeSignup(page: Page) {
  await expect(page.getByRole("heading", { name: "Welcome to BuildOne" })).toBeVisible();
  await page.getByLabel("I am 18 years old or older.").check();
  await page.getByLabel(/I accept the terms of use/).check();
  await page.getByRole("button", { name: "Create my account" }).click();
  // Wait until the account exists and the app has moved on, so the next navigation has a session.
  await expect(page).not.toHaveURL(/\/welcome/);
}
