// HARNESS STUB (app-level test fixture): the orderFixture testing/react-native-testing-library.md imports.
import type { Order } from "../api/types";

export const orderFixture = (over: Partial<Order> = {}): Order => ({
  id: "o0",
  status: "open",
  total_cents: 1000,
  note: "",
  created_at: "2026-09-30T00:00:00Z",
  ...over,
});
