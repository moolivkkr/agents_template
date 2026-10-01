---
skill: secure-rendering
description: DOM-XSS rules for UI code — HTML sinks only with DOMPurify, URL-scheme allowlist for href/src, markdown without raw HTML, safe redirects, postMessage origin checks, CSP-compatible code — and the XSS-RENDER test that proves them
version: "1.0"
tags:
  - security
  - xss
  - csp
  - rendering
  - ui
---

# Secure rendering — DOM XSS rules for UI code

> Code samples compile-checked: tsc (TypeScript 7.0.2, strict + noUncheckedIndexedAccess), and the XSS-RENDER checks ran in 3 Vitest 5.0.3 tests (jsdom 30.1, DOMPurify 3.4.16) (`tests/archetype-compile/ui-packs/run.sh`, 2026-09-30).

The API returns raw text: escaping belongs to **rendering**, and this file owns it (board review
2026-09-30, SEC-09). It complements `~/.claude/skills/security/secure-coding.md` §3–§4 (tokens, CSP
headers, CORS) and applies to React, Vue, Angular and Svelte, plus React Native `WebView`.

## Rules

1. **Text goes through the framework's escaping.** Use JSX `{value}`, Vue `{{ value }}`, Angular
   interpolation and Svelte `{value}`. Never build HTML strings from data.
2. **HTML sinks only take sanitized HTML.** These are sinks: `dangerouslySetInnerHTML`, `v-html`,
   `[innerHTML]`, `{@html}`, `innerHTML`/`outerHTML`/`insertAdjacentHTML`/`document.write`, and
   Angular `bypassSecurityTrust*`.
   - Pass a sink only HTML sanitized with **DOMPurify**, in the same component, at render time.
   - Add a comment with the reason, citing the FR.
   - Never trust "the server already sanitized it".
3. **URL sinks take an allowlisted scheme.** Before binding `href`, `src`, `action`/`formaction`,
   `window.location`, `window.open` or an iframe `src`, allow only `https:`, `http:`, `mailto:` and
   `tel:`, or a same-origin relative path.
   - Reject `javascript:`, `vbscript:` and `data:`; the only `data:` exception is an image URL your own
     code created.
   - Don't count on the framework to block `javascript:` URLs.
4. **Markdown and rich text:** render with raw HTML disabled (e.g. `react-markdown` without
   `rehype-raw`), or sanitize the output with DOMPurify. Link URLs still go through rule 3.
5. **No code from data:** no `eval`, no `new Function`, no string `setTimeout`/`setInterval`, and no
   dynamic `import()` of anything user-influenced.
6. **Redirect targets** (`returnTo`, `next`, `redirect`) accept only a same-origin path: it starts
   with one `/`, not `//` and not `/\`. Anything else goes to `/` (open redirect).
7. **`postMessage`:** check `event.origin` against an allowlist before reading `event.data`, and never
   send data with `targetOrigin: "*"`.
8. **Links to user-supplied URLs** open with `target="_blank" rel="noopener noreferrer"`.
9. **CSP-compatible code:** no inline `<script>`, no `on*=` attribute handlers in HTML strings, no
   `unsafe-eval` dependency. The server's CSP (`secure-coding.md` §4) must work unmodified.
10. **Untrusted content includes** anything a user or tenant entered, anything from a third-party
    API, uploaded file contents, and **LLM output**. Render all of it as text or sanitized markdown.
    Server error messages (`error.message`) render as text too.
11. **Third-party scripts:** only the ones the spec names. From a CDN, load them with Subresource
    Integrity (`integrity=` + `crossorigin`).
12. **React Native `WebView`:** set `originWhitelist` to your own origins, keep `allowFileAccess` off,
    check the origin in `onMessage`, and expose no privileged bridge to web content.

```tsx
// lib/safe-render.tsx
import DOMPurify from "dompurify";
import { useMemo } from "react";

// Reason: rich-text descriptions from the editor (FR-012). Sanitized here, at render time.
export function SafeHtml({ html }: { html: string }) {
  const clean = useMemo(() => DOMPurify.sanitize(html, { USE_PROFILES: { html: true } }), [html]);
  return <div dangerouslySetInnerHTML={{ __html: clean }} />;
}

const SAFE_SCHEMES = new Set(["https:", "http:", "mailto:", "tel:"]);
export function safeHref(raw: string | null | undefined): string | undefined {
  if (!raw) return undefined;
  try {
    const url = new URL(raw, window.location.origin);
    return SAFE_SCHEMES.has(url.protocol) ? url.href : undefined; // javascript:, data:, vbscript: → no link
  } catch {
    return undefined;
  }
}

export function safeReturnTo(raw: string | null): string {
  return raw && raw.startsWith("/") && !raw.startsWith("//") && !raw.startsWith("/\\") ? raw : "/";
}

// Usage: <a href={safeHref(user.website)} target="_blank" rel="noopener noreferrer">{user.website}</a>
```

## The test that proves it (abuse-matrix row `XSS-RENDER`)

For every screen that renders user-controlled text:
1. Seed each text field with `<img src=x onerror="window.__xss=1">` and `"><svg onload=window.__xss=1>`.
2. Seed each URL field with `javascript:window.__xss=1`.
3. Render the screen (component test in jsdom for sinks; Playwright e2e for the real browser).
4. Assert:
   - `window.__xss` is `undefined`;
   - the payload is visible as literal text;
   - an anchor built from a bad URL has no `href`;
   - with the production CSP, no `securitypolicyviolation` event fires.

A companion `SESSION-STORAGE` check asserts that `localStorage` and `sessionStorage` hold no token
after login.

## Review grep (what `security_reviewer` searches the diff for)

```
dangerouslySetInnerHTML|v-html|\[innerHTML\]|\{@html|innerHTML\s*=|outerHTML|insertAdjacentHTML|document\.write|bypassSecurityTrust|eval\(|new Function|javascript:|postMessage\(|addEventListener\(["']message
```

Each hit is sanitized per rule 2 or 3, or it is a finding.
