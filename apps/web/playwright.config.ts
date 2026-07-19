import { defineConfig, devices } from "@playwright/test";

/**
 * ERDA visual/E2E suite (§14 P6 gate). Assumes the API (:8000) and the web dev
 * server (:3000) are already running — CI starts them before invoking. The
 * config does not spawn servers so a developer can point it at either a live
 * or a frozen-snapshot backend.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "list" : [["list"]],
  use: {
    baseURL: "http://localhost:3000",
    viewport: { width: 1440, height: 900 },
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        // deck.gl needs WebGL; headless Chromium has none unless we force the
        // software rasterizer (SwiftShader).
        launchOptions: {
          args: [
            "--enable-unsafe-swiftshader",
            "--use-gl=angle",
            "--use-angle=swiftshader",
            "--ignore-gpu-blocklist",
          ],
        },
      },
    },
  ],
});
