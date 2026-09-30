// HARNESS STUB: the project's query-options factories and schemas the page archetypes call. Built with
// the real TanStack Query v5 helpers, over the one response envelope (src/types/api.ts is extracted
// from api/response-envelope.md at run time), so the fragments are checked against that contract.
import { infiniteQueryOptions, queryOptions, useMutation } from "@tanstack/react-query";
import { z } from "zod";
import { fetcher } from "./api-client";

export interface Resource {
  id: string;
  name: string;
  email: string;
  role: string;
}

export const createUserSchema = z.object({
  name: z.string().min(1),
  email: z.email(),
  role: z.enum(["admin", "member"]),
  bio: z.string().max(500),
});
export const updateUserSchema = createUserSchema.extend({ version: z.number().int() });
export type CreateUserInput = z.infer<typeof createUserSchema>;
export type UpdateUserInput = z.infer<typeof updateUserSchema>;
export interface User extends UpdateUserInput {
  id: string;
}

export const profileSchema = z.object({ displayName: z.string().min(1), timezone: z.string() });
export const notifSchema = z.object({ email: z.boolean(), push: z.boolean() });
export type Profile = z.infer<typeof profileSchema>;
export type NotificationSettings = z.infer<typeof notifSchema>;

export const resourceQueries = {
  list: (filters: { search: string; sort: string }) =>
    infiniteQueryOptions({
      queryKey: ["resources", "list", filters] as const,
      queryFn: ({ pageParam }) =>
        fetcher<Resource[]>(`/resources?${new URLSearchParams({ q: filters.search, sort: filters.sort, cursor: pageParam ?? "" })}`),
      initialPageParam: undefined as string | undefined,
      getNextPageParam: (last) => (last.meta.pagination?.has_more ? (last.meta.pagination.next_cursor ?? undefined) : undefined),
    }),
  detail: (id: string | undefined) =>
    queryOptions({
      queryKey: ["resources", "detail", id] as const,
      queryFn: () => fetcher<Resource>(`/resources/${id}`),
      enabled: !!id,
    }),
};

export const userQueries = {
  detail: (id: string) =>
    queryOptions({ queryKey: ["users", "detail", id] as const, queryFn: () => fetcher<User>(`/users/${id}`) }),
};

export const settingsQueries = {
  profile: () => queryOptions({ queryKey: ["settings", "profile"] as const, queryFn: () => fetcher<Profile>("/settings/profile") }),
  notifications: () =>
    queryOptions({ queryKey: ["settings", "notifications"] as const, queryFn: () => fetcher<NotificationSettings>("/settings/notifications") }),
  security: () =>
    queryOptions({ queryKey: ["settings", "security"] as const, queryFn: () => fetcher<{ twoFactor: boolean }>("/settings/security") }),
};

export const dashboardQueries = {
  stats: () => queryOptions({ queryKey: ["dashboard", "stats"] as const, queryFn: () => fetcher<{ users: number }>("/dashboard/stats") }),
  revenueChart: () =>
    queryOptions({ queryKey: ["dashboard", "revenue"] as const, queryFn: () => fetcher<Array<{ day: string; cents: number }>>("/dashboard/revenue") }),
  signupChart: () =>
    queryOptions({ queryKey: ["dashboard", "signups"] as const, queryFn: () => fetcher<Array<{ day: string; count: number }>>("/dashboard/signups") }),
  recentActivity: () =>
    queryOptions({ queryKey: ["dashboard", "activity"] as const, queryFn: () => fetcher<Array<{ id: string; text: string }>>("/dashboard/activity") }),
};

export function useDeleteResource() {
  return useMutation({ mutationFn: (id: string) => fetcher<null>(`/resources/${id}`, { method: "DELETE" }) });
}

export function useCreateUser() {
  return useMutation({ mutationFn: (input: CreateUserInput) => fetcher<User>("/users", { method: "POST", body: JSON.stringify(input) }) });
}

export function useUpdateProfile() {
  return useMutation({ mutationFn: (input: Profile) => fetcher<Profile>("/settings/profile", { method: "PUT", body: JSON.stringify(input) }) });
}
