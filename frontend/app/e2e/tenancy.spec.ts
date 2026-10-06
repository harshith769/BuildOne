import { expect, test } from "@playwright/test";

import { completeSignup, signInWithFakeIdp, uniqueEmail } from "./helpers";

// Full stack (S3, S4, invitations): create a company, invite a second person who signs up from the link,
// change their role, remove them; switch between two organisations.

test("owner creates a company, invites, changes a role and removes a member", async ({ page, browser }) => {
  const ownerEmail = uniqueEmail("owner");
  const inviteeEmail = uniqueEmail("invitee");

  await page.goto("/");
  await signInWithFakeIdp(page, ownerEmail, "Olga Owner");
  await completeSignup(page);
  await expect(page.getByText("You don't belong to an organisation yet.")).toBeVisible();

  // S3
  await page.getByRole("link", { name: "Create an organisation" }).click();
  await page.getByLabel("Company", { exact: true }).check();
  await page.getByLabel("Name").fill("Acme E2E");
  await page.getByRole("button", { name: "Create" }).click();
  await expect(page.getByRole("heading", { name: "Acme E2E" })).toBeVisible();
  await expect(page.getByTestId("member-row")).toHaveCount(1);
  await expect(page.getByText("(you)")).toBeVisible();

  // S4: invite as viewer; the link is shown once.
  await page.getByLabel("Email").fill(inviteeEmail);
  await page.getByRole("combobox", { name: "Role", exact: true }).selectOption("viewer");
  await page.getByRole("button", { name: "Invite" }).click();
  const link = await page.getByLabel("Invitation link").inputValue();
  expect(link).toMatch(/\/invite#token=/);
  await expect(page.getByText(inviteeEmail).last()).toBeVisible();

  // The invitee opens the link in their own browser, signs up, and accepts.
  const inviteeContext = await browser.newContext();
  const invitee = await inviteeContext.newPage();
  await invitee.goto(link);
  await expect(invitee).toHaveURL(/\/sign-in/);
  await signInWithFakeIdp(invitee, inviteeEmail, "Vik Viewer");
  await completeSignup(invitee);
  await expect(invitee.getByRole("heading", { name: "Join Acme E2E" })).toBeVisible();
  await invitee.getByRole("button", { name: "Accept invitation" }).click();
  await expect(invitee.getByRole("heading", { name: "Acme E2E" })).toBeVisible();
  await expect(invitee.getByText("Viewer (read-only)").first()).toBeVisible();
  await expect(invitee.getByRole("heading", { name: "Invite people" })).toHaveCount(0);

  // Owner sees the new member, makes them a member, then removes them.
  await page.reload();
  await expect(page.getByTestId("member-row")).toHaveCount(2);
  await page.getByRole("combobox", { name: "Role of Vik Viewer" }).selectOption("member");
  await page.reload();
  await expect(page.getByRole("combobox", { name: "Role of Vik Viewer" })).toHaveValue("member");
  await page.getByTestId("member-row").filter({ hasText: "Vik Viewer" }).getByRole("button", { name: "Remove" }).click();
  await expect(page.getByTestId("member-row")).toHaveCount(1);

  await invitee.reload();
  await expect(invitee.getByRole("heading", { name: "Organisation not found" })).toBeVisible();
  await inviteeContext.close();
});

test("a user switches between two organisations", async ({ page }) => {
  await page.goto("/");
  await signInWithFakeIdp(page, uniqueEmail("switcher"), "Sam Switcher");
  await completeSignup(page);

  for (const [kind, name] of [
    ["Company", "Alpha Pvt Ltd"],
    ["Founding team (not incorporated yet)", "Beta Team"],
  ] as const) {
    await page.goto("/orgs/new");
    await page.getByLabel(kind, { exact: true }).check();
    await page.getByLabel("Name").fill(name);
    await page.getByRole("button", { name: "Create" }).click();
    await expect(page.getByRole("heading", { name })).toBeVisible();
  }

  const switcher = page.getByRole("combobox", { name: "Organisation" });
  await expect(switcher).toHaveValue(/.+/);
  await switcher.selectOption({ label: "Alpha Pvt Ltd" });
  await expect(page.getByRole("heading", { name: "Alpha Pvt Ltd" })).toBeVisible();
  await switcher.selectOption({ label: "Beta Team" });
  await expect(page.getByRole("heading", { name: "Beta Team" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Alpha Pvt Ltd" })).toHaveCount(0);
});
