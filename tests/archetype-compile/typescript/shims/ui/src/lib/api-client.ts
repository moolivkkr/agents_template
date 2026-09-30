// HARNESS STUB mirroring ui/api-integration-patterns.md: the error the project's fetcher throws for an
// error envelope, and the fetcher's signature (it resolves to the success envelope).
import type { ApiSuccess, FieldError } from "../types/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: FieldError[] = [],
    public requestId?: string,
    public retryable = false,
  ) {
    super(message);
  }
}

export declare function fetcher<T>(path: string, init?: RequestInit): Promise<ApiSuccess<T>>;
