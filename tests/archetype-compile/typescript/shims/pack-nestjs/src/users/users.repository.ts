// HARNESS STUB: the users repository frameworks/nestjs.md's service injects. An abstract class, so it is a
// DI token (an interface has no runtime value to inject by).
export interface User {
  id: string;
  tenantId: string;
  email: string;
  passwordHash: string;
  createdAt: Date;
}

export abstract class UsersRepository {
  abstract findByEmail(tenantId: string, email: string): Promise<User | null>;
  abstract create(tenantId: string, input: { email: string; password: string }): Promise<User>;
}
