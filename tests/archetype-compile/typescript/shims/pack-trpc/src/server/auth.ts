// HARNESS STUB: the project's token verifier frameworks/trpc.md's context calls.
export interface AuthUser {
  id: string;
  tenantId: string;
  roles: string[];
}

export declare function getUserFromToken(authorization: string | undefined): Promise<AuthUser | null>;
