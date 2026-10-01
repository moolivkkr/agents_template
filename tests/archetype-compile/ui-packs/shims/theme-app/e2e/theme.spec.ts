// HARNESS PROBE: the Tailwind CSS v4 / shadcn token CSS of ui/tailwind.md and ui/shadcn.md, built by `next build`
// with @tailwindcss/postcss, resolves in a real browser. For every token utility on the probe page the computed
// color equals the token's own value (read from the extracted app/globals.css, last declaration wins, so the
// shadcn.md overrides count), in light and in dark; --radius drives rounded-lg; opacity modifiers produce a
// translucent mix; and ui/component-composition.md's Alert variants pass axe's WCAG 2 AA color-contrast rule.
import { readFileSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const css = readFileSync("src/app/globals.css", "utf8");

function tokens(selector: ":root" | ".dark"): Record<string, string> {
  const out: Record<string, string> = {};
  const block = new RegExp(`(?:^|\\n)${selector.replace(".", "\\.")}\\s*\\{([^}]*)\\}`, "g");
  for (const b of css.matchAll(block)) {
    for (const d of (b[1] ?? "").matchAll(/--([\w-]+):\s*([^;]+);/g)) out[d[1]!] = d[2]!.trim();
  }
  return out;
}
const LIGHT = tokens(":root");
const DARK = { ...LIGHT, ...tokens(".dark") };

/** Any CSS color painted on a canvas → [r, g, b, a]. The build's Lightning CSS pass rewrites oklch() tokens as
 *  lab() (plus a hex fallback), so colors are compared as pixels, never as strings. */
const rgba = (page: Page, color: string) =>
  page.evaluate((c) => {
    const ctx = document.createElement("canvas").getContext("2d")!;
    ctx.clearRect(0, 0, 1, 1);
    ctx.fillStyle = c;
    ctx.fillRect(0, 0, 1, 1);
    return Array.from(ctx.getImageData(0, 0, 1, 1).data);
  }, color);

const style = (page: Page, testId: string, prop: string) =>
  page.getByTestId(testId).evaluate((el, p) => getComputedStyle(el).getPropertyValue(p), prop);

async function expectSameColor(page: Page, actual: string, literal: string, label: string) {
  const [a, b] = [await rgba(page, actual), await rgba(page, literal)];
  expect(a.every((v, i) => Math.abs(v - b[i]!) <= 2), `${label}: ${actual} [${a}] vs ${literal} [${b}]`).toBe(true);
}

/** Switch to dark with CSS transitions off first: the shadcn Button animates background-color, so sampling
 *  right after the class change read an in-between colour (flaky: 3 runs gave 3 different values). */
async function goDark(page: Page) {
  await page.addStyleTag({ content: "*, *::before, *::after { transition: none !important; animation: none !important; }" });
  await page.evaluate(() => document.documentElement.classList.add("dark"));
}

const PAIRS: Array<[testId: string, prop: string, token: string]> = [
  ["bg-background", "background-color", "background"],
  ["bg-background", "color", "foreground"],
  ["bg-primary", "background-color", "primary"],
  ["bg-primary", "color", "primary-foreground"],
  ["bg-secondary", "background-color", "secondary"],
  ["bg-card", "background-color", "card"],
  ["bg-card", "color", "card-foreground"],
  ["bg-muted", "background-color", "muted"],
  ["bg-muted", "color", "muted-foreground"],
  ["bg-accent", "background-color", "accent"],
  ["bg-destructive", "background-color", "destructive"],
  ["bg-warning", "background-color", "warning"],
  ["bg-success", "background-color", "success"],
  ["border-border", "border-top-color", "border"],
  ["button", "background-color", "primary"],
];

async function expectTokens(page: Page, values: Record<string, string>) {
  for (const [testId, prop, token] of PAIRS) {
    expect(values[token], `token --${token} is declared`).toBeTruthy();
    await expectSameColor(page, await style(page, testId, prop), values[token]!, `${testId} ${prop} = --${token}`);
  }
  // bg-primary/50: the token mixed to 50% alpha (color-mix), not transparent and not the opaque token
  const [, , , alpha] = await rgba(page, await style(page, "bg-primary-50", "background-color"));
  expect(alpha).toBeGreaterThan(110);
  expect(alpha).toBeLessThan(145);
  const radiusPx = `${parseFloat(values.radius!) * 16}px`; // --radius is in rem
  expect(await style(page, "rounded-lg", "border-top-left-radius")).toBe(radiusPx);
}

test("light: every token utility resolves to its token (shadcn.md overrides applied)", async ({ page }) => {
  expect(LIGHT.primary, "shadcn.md's override is the last :root --primary").toBe("oklch(0.488 0.243 264.376)");
  await page.goto("/");
  await expectTokens(page, LIGHT);
});

test("dark: the .dark values apply through the dark variant class", async ({ page }) => {
  await page.goto("/");
  await goDark(page);
  await expectTokens(page, DARK);
});

for (const mode of ["light", "dark"] as const) {
  test(`${mode}: Alert variants use the tokens and pass WCAG 2 AA color contrast`, async ({ page }) => {
    await page.goto("/");
    if (mode === "dark") await goDark(page);
    const values = mode === "dark" ? DARK : LIGHT;
    const alerts = page.getByTestId("alerts").locator('[role="alert"]');
    await expect(alerts).toHaveCount(4);
    for (const [i, token] of [[1, "destructive"], [2, "warning"], [3, "success"]] as const) {
      const color = await alerts.nth(i).evaluate((el) => getComputedStyle(el).color);
      await expectSameColor(page, color, values[token]!, `${token} alert text = --${token}`);
    }
    const results = await new AxeBuilder({ page }).include('[data-testid="alerts"]').withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" ")}`)).toEqual([]);
  });
}
