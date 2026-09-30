// HARNESS STUB: safeHref / safeReturnTo exactly as ui/secure-rendering.md defines them (plain TS there,
// inside a TSX block with a React component, so run.sh can't extract it). The packs import this module.
const SAFE_SCHEMES = new Set(["https:", "http:", "mailto:", "tel:"])

export function safeHref(raw: string | null | undefined): string | undefined {
  if (!raw) return undefined
  try {
    const url = new URL(raw, window.location.origin)
    return SAFE_SCHEMES.has(url.protocol) ? url.href : undefined
  } catch {
    return undefined
  }
}

export function safeReturnTo(raw: unknown): string {
  return typeof raw === "string" && raw.startsWith("/") && !raw.startsWith("//") && !raw.startsWith("/\\") ? raw : "/"
}
