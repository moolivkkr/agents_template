// HARNESS STUB (app-level): the feature hook and presentational pieces frameworks/react-native-app-patterns.md's
// OrdersScreen composes. useOrders reads GET /api/v1/orders (the one envelope) through TanStack Query and
// returns the rows (`select`), so the screen's `data` is Order[]; the components carry the testIDs and names
// the RNTL tests select by.
import { Pressable, Text, View } from "react-native";
import { useQuery } from "@tanstack/react-query";
import type { ApiErrorBody, ApiSuccess, Order } from "../api/types";

const API = "http://localhost:8080/api/v1"; // E2E env config would give 10.0.2.2 on the Android emulator

export function useOrders() {
  return useQuery({
    queryKey: ["orders", "list"],
    queryFn: async (): Promise<ApiSuccess<Order[]>> => {
      const res = await fetch(`${API}/orders`);
      const body: unknown = await res.json();
      if (!res.ok) throw new Error((body as ApiErrorBody).error.message);
      return body as ApiSuccess<Order[]>;
    },
    select: (res) => res.data,
  });
}

export function OrdersSkeleton({ testID }: { testID: string }) {
  return <View testID={testID} accessibilityLabel="Loading orders" />;
}

export function ErrorState({ testID, onRetry }: { testID: string; onRetry: () => void }) {
  return (
    <View testID={testID}>
      <Text>Couldn't load orders.</Text>
      <Pressable role="button" aria-label="Retry" onPress={onRetry} hitSlop={8}>
        <Text>Retry</Text>
      </Pressable>
    </View>
  );
}

export function EmptyState({ testID, actionLabel }: { testID: string; actionLabel: string }) {
  return (
    <View testID={testID}>
      <Text>No orders yet</Text>
      <Pressable role="button" aria-label={actionLabel}>
        <Text>{actionLabel}</Text>
      </Pressable>
    </View>
  );
}

export function OrderRow({ order, testID }: { order: Order; testID: string }) {
  return (
    <View testID={testID} accessible>
      <Text>Order {order.id}</Text>
    </View>
  );
}
