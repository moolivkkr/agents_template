
// ── HARNESS STUB: payload types a project generates from data-contracts.md / OpenAPI ──────────────
// run.sh writes <root>/api/types.ts = the envelope types from api/response-envelope.md (extracted at
// run time) + these payload types. Packs import both from that one module, as a project would.
export type Order = {
  id: string
  customer_name: string
  customer_email: string
  quantity: number
  status: "open" | "paid" | "cancelled"
  total_cents: number
  created_at: string
}
export type CreateOrderInput = { customer_email: string; quantity: number; notes?: string }
export type SessionUser = { id: string; email: string; name: string }
