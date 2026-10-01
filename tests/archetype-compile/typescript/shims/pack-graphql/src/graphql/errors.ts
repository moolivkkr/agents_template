// HARNESS STUB: the project's domain-error → UserError mapping (null for anything that isn't a domain error),
// and the details[].code type: exactly the closed set in api/response-envelope.md.
import type { UserError } from "./types";

export type FieldCode =
  | "required"
  | "invalid_type"
  | "invalid_format"
  | "invalid_value"
  | "out_of_range"
  | "too_short"
  | "too_long"
  | "unknown_field"
  | "invalid_cursor"
  | "already_exists";

export declare function toUserError(err: unknown): UserError | null;
