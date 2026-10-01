// HARNESS STUB: the project's user service that frameworks/express.md's router calls (tenant-scoped).
export interface User {
  id: string;
  tenantId: string;
  email: string;
}

export declare const userService: {
  getById(tenantId: string, id: string): Promise<User>;
};
