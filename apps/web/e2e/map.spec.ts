import { expect, test } from "@playwright/test";

/** Map hero (§13.4) + the gate criterion: interactive < 2 s. */
test.describe("map hero", () => {
  test("map becomes interactive in under 2 seconds", async ({ page }) => {
    // Warm the route first so the measurement reflects production behaviour,
    // not the dev server's one-time chunk compile (the §14 gate is about the
    // built app; the map lazy-loads deck.gl on a warm bundle).
    const mapPanel = page.getByRole("region", { name: "Prospectivity map" });
    await page.goto("/");
    await mapPanel.getByText(/wells/).waitFor({ state: "visible" });
    await page.reload();

    // interactive = the map canvas is up and the wells layer's data has loaded
    // (the legend reports the count only once the payload is in hand).
    const start = Date.now();
    await page.locator("canvas.maplibregl-canvas").first().waitFor({ state: "visible" });
    await expect(mapPanel.getByText(/[0-9,]+ wells/)).toBeVisible();
    const elapsed = Date.now() - start;
    expect(elapsed, `map interactive in ${elapsed}ms`).toBeLessThan(2000);
  });

  test("states the §9.8 no-heatmap boundary and well legend", async ({ page }) => {
    await page.goto("/");
    const mapPanel = page.getByRole("region", { name: "Prospectivity map" });
    await expect(mapPanel).toContainText("NO PROSPECTIVITY HEATMAP");
    await expect(mapPanel).toContainText("oil");
    await expect(mapPanel).toContainText("gas");
    await expect(mapPanel).toContainText("wells");
  });

  test("clicking the map opens a block card with user-supplied Pg", async ({ page }) => {
    await page.goto("/");
    const canvas = page.locator("canvas.maplibregl-canvas").first();
    await canvas.waitFor({ state: "visible" });
    await page.waitForTimeout(1500); // let land + wells render
    const box = await canvas.boundingBox();
    if (!box) throw new Error("no map canvas");
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    await expect(page.getByText("BLOCK PICK")).toBeVisible();
    await expect(page.getByText("Pg is a scenario input")).toBeVisible();
    await expect(page.getByRole("button", { name: /GENERATE MEMO/ })).toBeVisible();
  });
});
