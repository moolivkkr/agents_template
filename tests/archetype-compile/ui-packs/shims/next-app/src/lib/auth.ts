// HARNESS STUB (app-level): the project's session check, the one frameworks/nextjs.md's Server Action calls.
// A real one verifies the session cookie against the session store and checks the role.
import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export type Session = { userId: string; tenantId: string; role: "admin" | "member" | "viewer" };

export async function requireSession(opts: { role?: Session["role"] } = {}): Promise<Session> {
  const sid = (await cookies()).get("session")?.value;
  if (!sid) redirect("/login");
  const session: Session = { userId: "u1", tenantId: "t1", role: "admin" };
  if (opts.role && session.role !== opts.role) throw new Error("FORBIDDEN");
  return session;
}
