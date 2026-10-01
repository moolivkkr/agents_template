// HARNESS STUB: the project's domain-error → UserError mapping (null for anything that isn't a domain error).
import type { UserError } from "./types";

export declare function toUserError(err: unknown): UserError | null;
