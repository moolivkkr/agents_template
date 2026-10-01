// HARNESS: Playwright config for the theme probe (system Chrome, the `next start` server the harness runs).
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  retries: 0,
  forbidOnly: true,
  reporter: [["list"]],
  use: { baseURL: process.env.APP_BASE_URL, channel: "chrome" },
});
