// HARNESS STUB: the project's data access frameworks/trpc.md's procedures call (tenant-scoped, cursor pages).
export interface User {
  id: string;
  tenantId: string;
  email: string;
  name: string;
}

export declare const db: {
  users: {
    list(tenantId: string, page: { cursor?: string | undefined; limit: number }): Promise<{
      items: User[];
      nextCursor: string | null;
    }>;
    create(tenantId: string, input: { email: string; name: string }): Promise<User>;
  };
};
