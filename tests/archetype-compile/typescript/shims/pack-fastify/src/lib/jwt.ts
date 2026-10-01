// HARNESS STUB: the project's JWT verifier that frameworks/fastify.md's auth plugin calls (the real one checks
// signature, exp, iss and aud — backend/archetypes/auth-middleware-typescript.md). Here the token from
// src/test/helpers.ts is valid and anything else is rejected, so the inject() tests run in-process.
export interface Claims {
  userId: string;
  tenantId: string;
  roles: string[];
}

export const TEST_TOKEN = "harness-test-token-tenant-a";

export async function verifyJwt(token: string): Promise<Claims> {
  if (token !== TEST_TOKEN) throw new Error("invalid token");
  return { userId: "user-a", tenantId: "tenant-a", roles: ["member"] };
}
