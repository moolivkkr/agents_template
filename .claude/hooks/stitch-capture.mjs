#!/usr/bin/env node
// stitch-capture.mjs — capture every page of a running app for /stitch import (skills/ui/stitch-design.md §3).
//
// The Stitch MCP can't take an image, so /stitch import recreates each existing page from a description.
// This script produces that description's raw material, per route and viewport:
//   <out>/<route-slug>/<viewport>/screenshot.png   full-page screenshot
//   <out>/<route-slug>/<viewport>/capture.json     { route, viewport, url, title, status,
//        outline: { landmarks[], headings[], controls[], tables[], lists[], images[], regions[] },
//        aria: Playwright ARIA snapshot (YAML text) when available,
//        text: visible text (trimmed), tokens: computed colours / fonts / sizes / radii / spacing with counts }
// and, across all pages:
//   <out>/index.json          every capture, with errors per route
//   <out>/design-tokens.json  tokens merged over every page (most-used first)
//   <out>/DESIGN.md           a draft design system derived from those tokens (upload_design_md input)
//
// Routes: --routes /a,/b  and/or  --manifest agent_state/phases/N/ui_developer/manifest.json (screens[].route;
// repeatable). Routes with parameters (/orders/:id) need --param id=123 or are skipped and reported.
//
// Usage:
//   node .claude/hooks/stitch-capture.mjs --base-url "$APP_BASE_URL" --out agent_state/stitch/import \
//        [--routes /,/orders] [--manifest …] [--viewports desktop,mobile] [--param id=42] \
//        [--storage-state auth.json] [--wait-ms 500] [--max-text 4000]
// Playwright: resolved from STITCH_PLAYWRIGHT_DIR, then the project (cwd) — @playwright/test or playwright.
// Browser: STITCH_CAPTURE_CHANNEL (default "chrome", the system Chrome; falls back to Playwright's chromium).
// Exit: 0 every route captured, 1 some routes failed (see index.json), 2 usage / no Playwright.
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const VIEWPORTS = {
  desktop: { width: 1280, height: 800, deviceScaleFactor: 1, isMobile: false, hasTouch: false, device: "DESKTOP" },
  mobile: { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true, device: "MOBILE" },
};

function parseArgs(argv) {
  const a = { routes: [], manifests: [], params: {}, viewports: ["desktop", "mobile"], waitMs: 500, maxText: 4000 };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i], v = argv[i + 1];
    const take = () => { i++; return v; };
    if (k === "--base-url") a.baseUrl = take();
    else if (k === "--out") a.out = take();
    else if (k === "--routes") a.routes.push(...take().split(",").map((s) => s.trim()).filter(Boolean));
    else if (k === "--manifest") a.manifests.push(take());
    else if (k === "--viewports") a.viewports = take().split(",").map((s) => s.trim());
    else if (k === "--param") { const [pk, ...pv] = take().split("="); a.params[pk] = pv.join("="); }
    else if (k === "--storage-state") a.storageState = take();
    else if (k === "--wait-ms") a.waitMs = Number(take());
    else if (k === "--max-text") a.maxText = Number(take());
    else if (k === "-h" || k === "--help") a.help = true;
    else { console.error(`stitch-capture: unknown argument ${k}`); process.exit(2); }
  }
  return a;
}

async function loadPlaywright() {
  const bases = [process.env.STITCH_PLAYWRIGHT_DIR, process.cwd()].filter(Boolean);
  for (const base of bases) {
    const req = createRequire(path.join(path.resolve(base), "noop.js"));
    for (const name of ["@playwright/test", "playwright", "playwright-core"]) {
      try {
        const mod = await import(pathToFileURL(req.resolve(name)).href);
        const chromium = mod.chromium || mod.default?.chromium;
        if (chromium) return chromium;
      } catch { /* try the next */ }
    }
  }
  return null;
}

export function slugFor(route) {
  const s = route.replace(/^\/+|\/+$/g, "").replace(/[^a-zA-Z0-9]+/g, "-").replace(/^-|-$/g, "").toLowerCase();
  return s || "home";
}

function fillParams(route, params) {
  let missing = null;
  const filled = route.replace(/:([A-Za-z_][A-Za-z0-9_]*)|\[([A-Za-z_][A-Za-z0-9_]*)\]/g, (m, a, b) => {
    const k = a || b;
    if (params[k] === undefined) { missing = k; return m; }
    return encodeURIComponent(params[k]);
  });
  return { filled, missing };
}

// Runs in the page. Kept dependency-free and defensive: it must work on any app.
function pageProbe(maxText) {
  const vis = (el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== "hidden" && cs.display !== "none" && cs.opacity !== "0";
  };
  const box = (el) => { const r = el.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y + scrollY), Math.round(r.width), Math.round(r.height)]; };
  const txt = (s) => (s || "").replace(/\s+/g, " ").trim().slice(0, 120);
  const labelOf = (el) => {
    if (el.getAttribute("aria-label")) return el.getAttribute("aria-label");
    const by = el.getAttribute("aria-labelledby");
    if (by) return by.split(/\s+/).map((id) => document.getElementById(id)?.innerText || "").join(" ");
    if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) return l.innerText; }
    const wrap = el.closest("label"); if (wrap) return wrap.innerText;
    return el.getAttribute("placeholder") || el.getAttribute("name") || el.getAttribute("title") || "";
  };
  const LANDMARK = { HEADER: "banner", NAV: "navigation", MAIN: "main", ASIDE: "complementary", FOOTER: "contentinfo", FORM: "form" };
  const landmarks = [];
  for (const el of document.querySelectorAll("header,nav,main,aside,footer,form,[role]")) {
    if (!vis(el)) continue;
    const role = el.getAttribute("role") || LANDMARK[el.tagName];
    if (!["banner", "navigation", "main", "complementary", "contentinfo", "form", "search", "region", "dialog", "tablist"].includes(role)) continue;
    landmarks.push({ role, name: txt(el.getAttribute("aria-label") || ""), box: box(el) });
  }
  const headings = [...document.querySelectorAll("h1,h2,h3,h4,h5,h6,[role=heading]")].filter(vis)
    .map((h) => ({ level: Number(h.getAttribute("aria-level") || h.tagName.slice(1)) || 2, text: txt(h.innerText), box: box(h) }))
    .filter((h) => h.text);
  const controls = [];
  for (const el of document.querySelectorAll("button,[role=button],a[href],input,select,textarea,[role=tab],[role=switch],[role=checkbox]")) {
    if (!vis(el)) continue;
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute("type") || "").toLowerCase();
    let kind = tag === "a" ? "link" : (tag === "button" || el.getAttribute("role") === "button" || ["submit", "button"].includes(type)) ? "button"
      : ["input", "select", "textarea"].includes(tag) ? "field" : el.getAttribute("role") || tag;
    if (type === "hidden") continue;
    const name = kind === "field" ? labelOf(el) : (el.getAttribute("aria-label") || el.innerText || el.getAttribute("title") || el.value || "");
    controls.push({ kind, name: txt(name), type: type || undefined, box: box(el) });
  }
  const tables = [...document.querySelectorAll("table,[role=table],[role=grid]")].filter(vis).map((t) => ({
    columns: [...t.querySelectorAll("th,[role=columnheader]")].map((c) => txt(c.innerText)).filter(Boolean),
    rows: t.querySelectorAll("tbody tr,[role=row]").length, box: box(t),
  }));
  const lists = [...document.querySelectorAll("ul,ol,[role=list]")].filter(vis)
    .map((l) => ({ items: l.querySelectorAll(":scope > li,[role=listitem]").length, box: box(l) })).filter((l) => l.items > 1);
  const images = [...document.querySelectorAll("img,svg[role=img],[role=img]")].filter(vis)
    .map((i) => ({ alt: txt(i.getAttribute("alt") || i.getAttribute("aria-label") || ""), box: box(i) }));
  // Top-level layout regions: the large visible blocks directly under body / the app root.
  const root = document.querySelector("#root,#__next,#app,[data-reactroot]") || document.body;
  const regions = [...root.querySelectorAll(":scope > *, :scope > * > *")].filter(vis)
    .map((el) => ({ tag: el.tagName.toLowerCase(), role: el.getAttribute("role") || LANDMARK[el.tagName] || null, box: box(el) }))
    .filter((r) => r.box[2] * r.box[3] > 0.04 * innerWidth * innerHeight).slice(0, 24);
  // Design tokens: computed styles over visible elements, counted.
  const count = (m, k) => { if (k && k !== "0px" && k !== "normal" && k !== "rgba(0, 0, 0, 0)" && k !== "transparent") m[k] = (m[k] || 0) + 1; };
  const t = { color: {}, background: {}, border: {}, fontFamily: {}, fontSize: {}, fontWeight: {}, lineHeight: {}, radius: {}, spacing: {}, shadow: {} };
  let n = 0;
  for (const el of document.body.querySelectorAll("*")) {
    if (n > 4000) break;
    if (!vis(el)) continue;
    n++;
    const cs = getComputedStyle(el);
    const hasText = [...el.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim());
    if (hasText) { count(t.color, cs.color); count(t.fontFamily, cs.fontFamily); count(t.fontSize, cs.fontSize); count(t.fontWeight, cs.fontWeight); count(t.lineHeight, cs.lineHeight); }
    count(t.background, cs.backgroundColor);
    if (parseFloat(cs.borderTopWidth) > 0) count(t.border, cs.borderTopColor);
    count(t.radius, cs.borderTopLeftRadius);
    for (const p of ["paddingTop", "paddingLeft", "marginTop", "marginBottom", "rowGap", "columnGap"]) count(t.spacing, cs[p]);
    if (cs.boxShadow && cs.boxShadow !== "none") count(t.shadow, cs.boxShadow);
  }
  const top = (m, k = 12) => Object.entries(m).sort((a, b) => b[1] - a[1]).slice(0, k).map(([value, count]) => ({ value, count }));
  const tokens = Object.fromEntries(Object.entries(t).map(([k, m]) => [k, top(m, k === "spacing" ? 16 : 12)]));
  tokens.bodyBackground = getComputedStyle(document.body).backgroundColor;
  tokens.colorScheme = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  return {
    title: document.title,
    outline: { landmarks, headings, controls, tables, lists, images, regions },
    text: (document.body.innerText || "").replace(/\n{3,}/g, "\n\n").trim().slice(0, maxText),
    tokens,
    page: { width: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight },
  };
}

function mergeTokens(captures) {
  const merged = {};
  for (const c of captures) for (const [k, list] of Object.entries(c.tokens || {})) {
    if (!Array.isArray(list)) continue;
    merged[k] = merged[k] || {};
    for (const { value, count } of list) merged[k][value] = (merged[k][value] || 0) + count;
  }
  return Object.fromEntries(Object.entries(merged).map(([k, m]) => [k, Object.entries(m).sort((a, b) => b[1] - a[1]).slice(0, 16).map(([value, count]) => ({ value, count }))]));
}

function rgbToHex(v) {
  const m = /rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(v || "");
  if (!m) return v;
  return "#" + [m[1], m[2], m[3]].map((x) => Number(x).toString(16).padStart(2, "0")).join("").toUpperCase();
}

export function designMd(tokens, meta) {
  const first = (k) => tokens[k]?.[0]?.value;
  const list = (k, n = 6, f = (x) => x) => (tokens[k] || []).slice(0, n).map((x) => `\`${f(x.value)}\` (${x.count})`).join(", ") || "—";
  const font = (first("fontFamily") || "system-ui").split(",")[0].replace(/["']/g, "").trim();
  const accents = (tokens.background || []).map((x) => rgbToHex(x.value)).filter((h) => !/^#(F{6}|F[0-9A-F]F[0-9A-F]F[0-9A-F]|0{6}|1[0-9A-F]1[0-9A-F]1[0-9A-F])$/i.test(h));
  return `# DESIGN.md — derived from the running app

> Draft written by \`.claude/hooks/stitch-capture.mjs\` from computed styles of ${meta.pages} page captures
> (${meta.baseUrl}, ${meta.at}). It describes what the app USES today, most-used first. Review it, correct the
> names, then \`/stitch import\` uploads it (\`upload_design_md\` → \`create_design_system_from_design_md\`).

## Colour
- Page background: \`${rgbToHex(tokens.bodyBackground?.[0]?.value || first("background") || "#FFFFFF")}\`
- Surfaces / fills: ${list("background", 8, rgbToHex)}
- Primary / accent candidates (non-neutral fills): ${accents.slice(0, 4).map((h) => `\`${h}\``).join(", ") || "—"}
- Text: ${list("color", 6, rgbToHex)}
- Borders: ${list("border", 4, rgbToHex)}
- Colour mode: ${tokens.colorScheme?.[0]?.value || "light"}

## Typography
- Font family: **${font}** (all: ${list("fontFamily", 3)})
- Type scale (px, by use): ${list("fontSize", 10)}
- Weights: ${list("fontWeight", 5)}
- Line heights: ${list("lineHeight", 6)}

## Shape and spacing
- Corner radius: ${list("radius", 6)}
- Spacing values (padding / margin / gap): ${list("spacing", 12)}
- Shadows: ${list("shadow", 3)}

## Rules for generated screens
- Use only the colours, type sizes, radii and spacing above; do not introduce new ones.
- Keep the existing layout regions (header, navigation, main content) and their order on every screen.
- Every input has a visible label; interactive targets are at least 44px on mobile; text meets WCAG AA contrast.
`;
}

async function main() {
  const a = parseArgs(process.argv.slice(2));
  if (a.help || !a.baseUrl || !a.out) {
    console.error("usage: stitch-capture.mjs --base-url URL --out DIR [--routes /a,/b] [--manifest M.json] [--viewports desktop,mobile] [--param k=v] [--storage-state F]");
    process.exit(a.help ? 0 : 2);
  }
  for (const m of a.manifests) {
    const j = JSON.parse(fs.readFileSync(m, "utf8"));
    for (const s of j.screens || []) if (s.route) a.routes.push(s.route);
  }
  a.routes = [...new Set(a.routes)];
  if (!a.routes.length) { console.error("stitch-capture: no routes (use --routes or --manifest)"); process.exit(2); }
  for (const v of a.viewports) if (!VIEWPORTS[v]) { console.error(`stitch-capture: unknown viewport ${v}`); process.exit(2); }
  const chromium = await loadPlaywright();
  if (!chromium) {
    console.error("stitch-capture: Playwright not found. Install it in the project (npm i -D @playwright/test) or set STITCH_PLAYWRIGHT_DIR to a directory whose node_modules has it.");
    process.exit(2);
  }
  const channel = process.env.STITCH_CAPTURE_CHANNEL ?? "chrome";
  let browser;
  try { browser = await chromium.launch(channel ? { channel } : {}); }
  catch (e) {
    if (!channel) throw e;
    console.error(`stitch-capture: channel "${channel}" unavailable (${String(e.message).split("\n")[0]}); using Playwright's chromium`);
    browser = await chromium.launch();
  }
  fs.mkdirSync(a.out, { recursive: true });
  const index = { base_url: a.baseUrl, at: new Date().toISOString(), viewports: a.viewports, captures: [], errors: [] };
  const all = [];
  try {
    for (const vpName of a.viewports) {
      const vp = VIEWPORTS[vpName];
      const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: vp.deviceScaleFactor,
        isMobile: vp.isMobile, hasTouch: vp.hasTouch, ...(a.storageState ? { storageState: a.storageState } : {}) });
      const page = await ctx.newPage();
      for (const route of a.routes) {
        const { filled, missing } = fillParams(route, a.params);
        if (missing) { index.errors.push({ route, viewport: vpName, error: `route parameter '${missing}' has no --param value` }); continue; }
        const dir = path.join(a.out, slugFor(route), vpName);
        fs.mkdirSync(dir, { recursive: true });
        const url = new URL(filled, a.baseUrl).href;
        try {
          const resp = await page.goto(url, { waitUntil: "load", timeout: 30000 });
          await page.waitForLoadState("networkidle", { timeout: 10000 }).catch(() => {});
          if (a.waitMs) await page.waitForTimeout(a.waitMs);
          const probe = await page.evaluate(pageProbe, a.maxText);
          let aria = null;
          try { aria = await page.locator("body").ariaSnapshot(); } catch { /* older Playwright: no ARIA snapshot */ }
          await page.screenshot({ path: path.join(dir, "screenshot.png"), fullPage: true });
          const cap = { route, viewport: vpName, deviceType: vp.device, url, status: resp ? resp.status() : null, ...probe, aria };
          fs.writeFileSync(path.join(dir, "capture.json"), JSON.stringify(cap, null, 2));
          all.push(cap);
          index.captures.push({ route, viewport: vpName, deviceType: vp.device, status: cap.status, dir: path.relative(a.out, dir),
            headings: probe.outline.headings.length, controls: probe.outline.controls.length, height: probe.page.height });
          console.log(`captured ${route} [${vpName}] → ${path.relative(process.cwd(), dir)} (${probe.outline.headings.length} headings, ${probe.outline.controls.length} controls)`);
        } catch (e) {
          index.errors.push({ route, viewport: vpName, error: String(e.message).split("\n")[0] });
          console.error(`FAILED ${route} [${vpName}]: ${String(e.message).split("\n")[0]}`);
        }
      }
      await ctx.close();
    }
  } finally {
    await browser.close();
  }
  const tokens = mergeTokens(all);
  tokens.bodyBackground = all.length ? [{ value: all[0].tokens.bodyBackground, count: all.length }] : [];
  tokens.colorScheme = all.length ? [{ value: all[0].tokens.colorScheme, count: all.length }] : [];
  fs.writeFileSync(path.join(a.out, "design-tokens.json"), JSON.stringify(tokens, null, 2));
  fs.writeFileSync(path.join(a.out, "DESIGN.md"), designMd(tokens, { pages: all.length, baseUrl: a.baseUrl, at: index.at }));
  fs.writeFileSync(path.join(a.out, "index.json"), JSON.stringify(index, null, 2));
  console.log(`stitch-capture: ${index.captures.length} capture(s), ${index.errors.length} error(s) → ${a.out}/index.json`);
  process.exit(index.errors.length ? 1 : 0);
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((e) => { console.error(`stitch-capture: ${e.stack || e}`); process.exit(2); });
}
