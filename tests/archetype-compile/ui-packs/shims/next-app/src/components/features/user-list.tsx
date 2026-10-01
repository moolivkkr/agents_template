// HARNESS STUB (app-level): the client UserList ui/api-integration-patterns.md's prefetching page renders. It
// reads the prefetched cache through the pack's own useUsers hook (hooks/use-users.ts).
"use client";
import { useUsers } from "@/hooks/use-users";

export function UserList() {
  const query = useUsers();
  const users = query.data?.pages.flatMap((p) => p.data) ?? [];
  if (query.isPending) return <p role="status">Loading users…</p>;
  if (query.isError) return <p role="alert">{query.error.message}</p>;
  return (
    <ul>
      {users.map((u) => (
        <li key={u.id}>{u.name}</li>
      ))}
    </ul>
  );
}
