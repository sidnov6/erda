/**
 * §12.4 screenshot loop: capture the shell (default state + open palette) for
 * design self-critique against the erda-design-system checklist.
 *
 * Usage: node apps/web/scripts/screenshot.mjs <outDir> [url]
 */
import { mkdirSync } from "node:fs";

import { chromium } from "playwright";

const outDir = process.argv[2] ?? "docs/evidence";
const url = process.argv[3] ?? "http://localhost:3000";

mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
});
await page.goto(url, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(300);
await page.screenshot({ path: `${outDir}/p0-shell.png` });

await page.keyboard.press("ControlOrMeta+k");
await page.waitForTimeout(250);
await page.screenshot({ path: `${outDir}/p0-palette.png` });

await browser.close();
console.log(`wrote ${outDir}/p0-shell.png, ${outDir}/p0-palette.png`);
