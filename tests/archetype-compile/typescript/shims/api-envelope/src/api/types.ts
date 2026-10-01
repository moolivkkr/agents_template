// HARNESS STUB: what `openapi-typescript openapi.yaml -o src/api/types.ts` (v7) emits for core/api-excellence.md's
// GET /api/v1/users — the generated `paths` / `operations` / `components` shape the sample indexes into.
export interface paths {
  "/api/v1/users": {
    parameters: { query?: never; header?: never; path?: never; cookie?: never };
    get: operations["listUsers"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
}

export interface components {
  schemas: {
    User: { id: string; email: string; name: string };
    ListUsersResponse: {
      data: components["schemas"]["User"][];
      meta: {
        request_id: string;
        pagination: { next_cursor: string | null; has_more: boolean; limit: number; total_count?: number };
      };
    };
  };
  responses: never;
  parameters: never;
  requestBodies: never;
  headers: never;
  pathItems: never;
}

export interface operations {
  listUsers: {
    parameters: {
      query?: { cursor?: string; limit?: number };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      200: {
        headers: { [name: string]: unknown };
        content: { "application/json": components["schemas"]["ListUsersResponse"] };
      };
    };
  };
}
