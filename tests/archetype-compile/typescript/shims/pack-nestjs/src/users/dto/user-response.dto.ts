// HARNESS STUB: the response DTO frameworks/nestjs.md's controller returns — no password hash in it.
import type { User } from "../users.repository";

export interface UserResponseDto {
  id: string;
  email: string;
  createdAt: string;
}

export function toUserResponse(user: User): UserResponseDto {
  return { id: user.id, email: user.email, createdAt: user.createdAt.toISOString() };
}
