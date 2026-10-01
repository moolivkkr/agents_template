// HARNESS CHECK (not a stub): the envelope types core/api-excellence.md restates must be IDENTICAL to the ones
// api/response-envelope.md defines (the file that wins). A drifted field fails this unit.
import type * as Envelope from "./api";
import type * as Excellence from "./api-excellence";

type Equal<X, Y> = (<T>() => T extends X ? 1 : 2) extends <T>() => T extends Y ? 1 : 2 ? true : false;

export const envelopeParity: [
  Equal<Envelope.ApiSuccess<{ id: string }>, Excellence.ApiSuccess<{ id: string }>>,
  Equal<Envelope.Pagination, Excellence.Pagination>,
  Equal<Envelope.ApiErrorBody, Excellence.ApiErrorBody>,
] = [true, true, true];
