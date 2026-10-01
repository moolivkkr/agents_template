// HARNESS STUB (app-level): the typed `api` object frameworks/tanstack-query.md's hooks call, returning the
// one envelope (api/response-envelope.md). Plain fetch; in the probe tests MSW answers it.
import type { ApiSuccess, CreateResourceInput, Resource } from "@/types/api";

export type Filters = { search?: string; status?: "active" | "inactive" };

const url = (path: string) => new URL(`/api/v1${path}`, globalThis.location?.origin ?? "http://localhost").toString();
async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as T;
}

export const api = {
  listResources: (f: Filters & { cursor?: string }) => {
    const qs = new URLSearchParams(Object.entries(f).filter((e): e is [string, string] => typeof e[1] === "string"));
    return fetch(url(`/resources?${qs}`)).then((r) => json<ApiSuccess<Resource[]>>(r));
  },
  getResource: (id: string) => fetch(url(`/resources/${encodeURIComponent(id)}`)).then((r) => json<ApiSuccess<Resource>>(r)),
  createResource: (input: CreateResourceInput) =>
    fetch(url("/resources"), { method: "POST", body: JSON.stringify(input), headers: { "Content-Type": "application/json" } }).then((r) =>
      json<ApiSuccess<Resource>>(r),
    ),
  deleteResource: async (id: string) => {
    const res = await fetch(url(`/resources/${encodeURIComponent(id)}`), { method: "DELETE" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  },
};
