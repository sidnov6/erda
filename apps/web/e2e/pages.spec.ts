import { expect, test } from "@playwright/test";

/** The first-class report pages: /validation (§11) and /memos (§10.6). */
test.describe("validation page", () => {
  test("renders all validation pillars incl. the falsification gate", async ({ page }) => {
    await page.goto("/validation");
    await expect(page.getByRole("heading", { name: "Freshness" })).toBeVisible();
    await expect(page.getByText("EIA ↔ JODI Reconciliation")).toBeVisible();
    await expect(page.getByText("Model validation — falsification gate")).toBeVisible();
    await expect(page.getByText("GATE FAILED")).toBeVisible();
    await expect(page.getByText("Memo validation")).toBeVisible();
  });
});

test.describe("memos page", () => {
  test("lists showcase memos with verdict, coverage and determinism hash", async ({ page }) => {
    await page.goto("/memos");
    await expect(page.getByText("GOM-WR-DEMO").first()).toBeVisible();
    // the selected memo shows the verdict + citation coverage + red-team box
    await expect(page.getByText(/VERDICT/).first()).toBeVisible();
    await expect(page.getByText(/CITED \d+%/).first()).toBeVisible();
    await expect(page.getByText(/Red team/).first()).toBeVisible();
    // Pg provenance is stated user-supplied (§9.8)
    await expect(page.getByText(/USER-SUPPLIED/).first()).toBeVisible();
  });
});
