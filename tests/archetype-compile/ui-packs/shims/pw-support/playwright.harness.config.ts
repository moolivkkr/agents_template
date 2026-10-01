// HARNESS: testing/playwright.md's playwright.config.ts unchanged, plus three harness-only adjustments:
//  * every project uses the system Chrome (`channel: "chrome"`), so no browser download is needed;
//  * video off: recording needs Playwright's ffmpeg build, which only `npx playwright install` downloads
//    (the harness downloads nothing but npm packages); traces and screenshots stay as the pack sets them;
//  * the "setup" project the pack's auth.setup.ts comment describes, so that file runs too.
import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

export default defineConfig({
  ...base,
  use: { ...base.use, video: "off" },
  projects: [
    { name: "setup", testMatch: /.*\.setup\.ts/, use: { channel: "chrome" } },
    ...(base.projects ?? []).map((p) => ({ ...p, use: { ...p.use, channel: "chrome", video: "off" as const } })),
  ],
});
