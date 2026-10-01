// HARNESS STUB (app-level screen): the UserList testing/msw.md's per-test overrides render — four states over
// GET /api/v1/users (the one envelope); the error state is an alert with the server's message and a Retry button.
import { useQuery } from "@tanstack/react-query";
import type { ApiErrorBody, ApiSuccess, User } from "../api/types";

async function listUsers(): Promise<ApiSuccess<User[]>> {
  const res = await fetch("/api/v1/users");
  const body: unknown = await res.json();
  if (!res.ok) throw new Error((body as ApiErrorBody).error.message);
  return body as ApiSuccess<User[]>;
}

export function UserList() {
  const { data, isPending, isError, error, refetch } = useQuery({ queryKey: ["users", "list"], queryFn: listUsers });
  if (isPending) return <p role="status">Loading users…</p>;
  if (isError)
    return (
      <div>
        <p role="alert">{error.message}</p>
        <button onClick={() => refetch()}>Retry</button>
      </div>
    );
  if (data.data.length === 0) return <p>No users found</p>;
  return <ul>{data.data.map((u) => <li key={u.id}>{u.name}</li>)}</ul>;
}
