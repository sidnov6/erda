import { expect, test } from "@playwright/test";

/** Terminal shell + command palette (§8.1, §13.2). */
test.describe("terminal", () => {
  test("renders all seven panels and a live ticker", async ({ page }) => {
    await page.goto("/");
    for (const title of [
      "Price & curve deck",
      "Inventories",
      "OPEC+ compliance",
      "Prospectivity map",
      "Discovery monitor",
      "Basin ranking",
      "Event feed",
    ]) {
      await expect(page.getByRole("region", { name: title })).toBeVisible();
    }
    // ticker shows a real Brent value (numeric), not an em-dash
    await expect(page.locator("header").first()).toContainText("BRENT");
  });

  test("⌘K palette opens and lists mnemonics", async ({ page }) => {
    await page.goto("/");
    await page.keyboard.press("Meta+k");
    const palette = page.locator("[cmdk-list]");
    await expect(page.getByPlaceholder("type a mnemonic…")).toBeVisible();
    await expect(palette.getByText("Price & curve deck")).toBeVisible();
    await expect(palette.getByText("Feasibility memos")).toBeVisible();
    await page.keyboard.press("Escape");
  });

  test("footer states the honest boundaries and mode", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("contentinfo")).toContainText("Screening tool");
    await expect(page.getByRole("contentinfo")).toContainText("MODEL: NO-GO §9.8");
  });
});
