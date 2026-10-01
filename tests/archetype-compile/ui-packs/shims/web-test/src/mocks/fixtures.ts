// HARNESS STUB (app-level test fixtures): typed fixture builders and an orders handler, the kind
// testing/msw.md's handlers.ts and test-case-traceability.md's example import from the project.
import { http } from "msw";
import type { Order, User } from "../api/types";
import { page } from "./envelope";

export const userFixture = (over: Partial<User> = {}): User => ({
  id: "u0",
  name: "Test User",
  email: "user@example.com",
  role: "member",
  avatar_url: null,
  active: true,
  created_at: "2026-09-30T00:00:00Z",
  updated_at: "2026-09-30T00:00:00Z",
  ...over,
});

export const order = (over: Partial<Order> = {}): Order => ({
  id: "o1",
  status: "open",
  total_cents: 1299,
  note: "",
  created_at: "2026-09-30T00:00:00Z",
  ...over,
});

export const ordersHandler = (orders: Order[]) => http.get("/api/v1/orders", () => page(orders));
