// HARNESS STUB (app-level test util): the project's renderWithProviders, as in ui/archetypes/component-test.md —
// a fresh QueryClient per test with retries off (a retried 503 would hide the error state).
import type { ReactElement, ReactNode } from "react";
import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

export function renderWithProviders(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const Wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return { user: userEvent.setup(), ...render(ui, { wrapper: Wrapper }) };
}
