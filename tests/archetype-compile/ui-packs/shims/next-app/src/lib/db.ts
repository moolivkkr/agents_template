// HARNESS STUB (app-level): the server-only data access module frameworks/nextjs.md's Server Component and
// Server Action call. In-memory; a real one is the project's repository layer.
import "server-only";

export type UserRow = { id: string; tenant_id: string; name: string; email: string; role: "admin" | "member" | "viewer"; password_hash: string };

const rows: UserRow[] = [{ id: "u1", tenant_id: "t1", name: "Ada", email: "ada@example.com", role: "admin", password_hash: "x" }];

export const db = {
  getUsers: async ({ tenantId }: { tenantId: string }): Promise<UserRow[]> => rows.filter((r) => r.tenant_id === tenantId),
  users: {
    create: async (data: Omit<UserRow, "id" | "password_hash">) => {
      const row = { ...data, id: `u${rows.length + 1}`, password_hash: "" };
      rows.push(row);
      return row;
    },
  },
};
