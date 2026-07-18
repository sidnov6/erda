/**
 * §12.4 screenshot loop: capture the terminal (+ palette) and any extra routes
 * for design self-critique against the erda-design-system checklist.
 *
 * Usage: node apps/web/scripts/screenshot.mjs <outDir> [prefix] [url]
 */
import { mkdirSync } from "node:fs";

import { chromium } from "playwright";

const outDir = process.argv[2] ?? "docs/evidence";
const prefix = process.argv[3] ?? "p0";
const url = process.argv[4] ?? "http://localhost:3000";

mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
});
await page.goto(url, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(600);
await page.screenshot({ path: `${outDir}/${prefix}-shell.png` });

await page.keyboard.press("ControlOrMeta+k");
await page.waitForTimeout(250);
await page.screenshot({ path: `${outDir}/${prefix}-palette.png` });
await page.keyboard.press("Escape");

await page.goto(`${url}/validation`, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(400);
await page.screenshot({ path: `${outDir}/${prefix}-validation.png`, fullPage: true });

await browser.close();
console.log(`wrote ${prefix}-{shell,palette,validation}.png in ${outDir}`);
