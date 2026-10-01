// HARNESS STUB: the cursor paginator testing/property-based.md's "pagination covers all items" property tests.
// An opaque cursor (the position, base64url) — the property checks the sample, this is just a correct pager.
export function paginate<T>(
  items: readonly T[],
  cursor: string | undefined,
  limit: number,
): { items: T[]; cursor: string; hasMore: boolean } {
  const start = cursor ? Number(Buffer.from(cursor, "base64url").toString()) : 0;
  const page = items.slice(start, start + limit);
  const next = start + page.length;
  return { items: page, cursor: Buffer.from(String(next)).toString("base64url"), hasMore: next < items.length };
}
