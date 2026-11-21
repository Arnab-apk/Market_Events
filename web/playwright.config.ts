import { defineConfig } from "@playwright/test";

// Expects the dev stack to be running already: `npm run dev` from the project root
// (Next.js on 3000, Python API on 8000). Override with PLAYWRIGHT_BASE_URL.
export default defineConfig({
  testDir: "./tests",
  testMatch: /.*\.spec\.ts$/,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000",
    // Uses the locally installed Chrome so no browser download is needed; set
    // PLAYWRIGHT_CHANNEL=chromium to use Playwright's bundled build instead.
    channel: process.env.PLAYWRIGHT_CHANNEL || "chrome",
    trace: "off",
  },
});
