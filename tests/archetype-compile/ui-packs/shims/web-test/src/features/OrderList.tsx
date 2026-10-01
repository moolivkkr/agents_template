// HARNESS STUB (app-level screen): the OrderList test-case-traceability.md's example renders — a skeleton
// while loading (data-testid orders.skeleton), then each order's note rendered as TEXT (React escapes it).
import { useQuery } from "@tanstack/react-query";
import type { ApiSuccess, Order } from "../api/types";

export function OrderList() {
  const { data } = useQuery({
    queryKey: ["orders", "list"],
    queryFn: async () => (await (await fetch("/api/v1/orders")).json()) as ApiSuccess<Order[]>,
  });
  if (!data) return <div data-testid="orders.skeleton" aria-busy="true">Loading orders…</div>;
  return <ul>{data.data.map((o) => <li key={o.id}>{o.note}</li>)}</ul>;
}
