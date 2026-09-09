import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("rentwise_token", "synthetic-import-session"));
});

test("adding screenshots preserves earlier choices and rejects more than eight", async ({ page }) => {
  await page.goto("/projects/import-check/import");
  const input = page.locator('input[type="file"]');
  const file = (name: string) => ({ name, mimeType: "image/png", buffer: Buffer.from("synthetic image") });
  await input.setInputFiles([file("first.png")]);
  await input.setInputFiles([file("second.png")]);
  await expect(page.getByText("2 images selected")).toBeVisible();
  await input.setInputFiles([file("first.png")]);
  await expect(page.getByText("2 images selected")).toBeVisible();
  await input.setInputFiles(Array.from({ length: 7 }, (_, i) => file(`extra-${i}.png`)));
  await expect(page.getByText("Choose up to 8 images, at most 10 MB each and 30 MB in total.")).toBeVisible();
  await expect(page.getByText("2 images selected")).toBeVisible();
});

test("mobile import explains data use and rejects excessive combined text", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/projects/import-check/import");
  await expect(page.getByText("Remove names, phone numbers", { exact: false })).toBeVisible();
  await page.getByLabel("Listing text", { exact: true }).fill("a".repeat(20000));
  await page.getByLabel("Your notes", { exact: false }).fill("b".repeat(10001));
  await page.getByRole("button", { name: "Save and start analysis" }).click();
  await expect(page.getByText("Keep listing, chat and notes within 30,000 characters in total.")).toBeVisible();
});
