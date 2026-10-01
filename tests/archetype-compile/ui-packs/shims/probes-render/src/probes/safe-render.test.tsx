// HARNESS PROBE: the XSS-RENDER checks of ui/secure-rendering.md, run against the pack's own helpers in jsdom.
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { SafeHtml, safeHref, safeReturnTo } from "@/lib/safe-render";

declare global {
  interface Window { __xss?: number }
}

describe("secure-rendering.md — SafeHtml / safeHref / safeReturnTo", () => {
  it("SafeHtml strips event handlers and script from rich text, keeping the markup", () => {
    const { container } = render(
      <SafeHtml html={'<p>Hi <b>there</b></p><img src=x onerror="window.__xss=1"><script>window.__xss=1</script><svg onload="window.__xss=1"></svg>'} />,
    );
    expect(container.querySelector("b")?.textContent).toBe("there");
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("[onerror]")).toBeNull();
    expect(container.querySelector("[onload]")).toBeNull();
    expect(window.__xss).toBeUndefined();
  });

  it("safeHref allows http(s)/mailto/tel and same-origin paths, rejects script and data URLs", () => {
    expect(safeHref("https://example.com/a")).toBe("https://example.com/a");
    expect(safeHref("mailto:ada@example.com")).toBe("mailto:ada@example.com");
    expect(safeHref("tel:+15551234")).toBe("tel:+15551234");
    expect(safeHref("/orders/1")).toBe("http://localhost:3000/orders/1");
    for (const bad of ["javascript:window.__xss=1", " JavaScript:alert(1)", "vbscript:msgbox(1)", "data:text/html,<script>1</script>"]) {
      expect(safeHref(bad)).toBeUndefined();
    }
    expect(safeHref(null)).toBeUndefined();
  });

  it("safeReturnTo keeps a same-origin path and sends everything else to /", () => {
    expect(safeReturnTo("/orders?status=open")).toBe("/orders?status=open");
    for (const bad of ["//evil.example", "/\\evil.example", "https://evil.example", "javascript:alert(1)", "", null]) {
      expect(safeReturnTo(bad)).toBe("/");
    }
  });
});
