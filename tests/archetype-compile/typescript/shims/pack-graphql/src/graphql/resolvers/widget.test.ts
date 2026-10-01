// HARNESS TEST (not from the doc): frameworks/graphql.md's TypeScript `widgets` resolver rejects `first`
// outside 1–100 (VALIDATION_FAILED with details[]) instead of clamping it — checked on the resolver and
// through graphql-js execution, as a client sees it.
import { buildSchema, graphql, GraphQLError, type GraphQLFieldResolver } from "graphql";
import { describe, expect, it, vi } from "vitest";
import type { Context } from "../context";
import { widgetResolvers } from "./widget";

function makeCtx() {
  const list = vi.fn(async () => ({ edges: [], pageInfo: { hasNextPage: false, endCursor: null } }));
  const ctx = {
    tenantId: "tenant-a",
    userId: "user-a",
    loaders: {} as Context["loaders"],
    widgetService: { list, get: vi.fn(), create: vi.fn() },
  } as unknown as Context;
  return { ctx, list };
}

describe("widgets(first): reject, never clamp", () => {
  it.each([
    [0, "out_of_range", "Must be from 1 to 100."],
    [-1, "out_of_range", "Must be from 1 to 100."],
    [101, "out_of_range", "Must be from 1 to 100."],
    [500, "out_of_range", "Must be from 1 to 100."],
    [2.5, "invalid_type", "Must be a whole number."],
  ])("first = %s → VALIDATION_FAILED %s, the service is not called", async (first, code, message) => {
    const { ctx, list } = makeCtx();
    const err = await widgetResolvers.Query.widgets(undefined, { first }, ctx).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(GraphQLError);
    expect((err as GraphQLError).extensions).toEqual({
      code: "VALIDATION_FAILED",
      details: [{ field: "first", code, message }],
    });
    expect(list).not.toHaveBeenCalled();
  });

  it.each([
    [1, 1],
    [100, 100],
    [undefined, 20],
  ])("first = %s → the service gets %s (unchanged)", async (first, expected) => {
    const { ctx, list } = makeCtx();
    await widgetResolvers.Query.widgets(undefined, first === undefined ? {} : { first }, ctx);
    expect(list).toHaveBeenCalledWith("tenant-a", expected, undefined, undefined);
  });

  it("through graphql-js: widgets(first: 500) answers an error with extensions.code, not 100 rows", async () => {
    const schema = buildSchema(`
      type PageInfo { hasNextPage: Boolean!, endCursor: String }
      type WidgetConnection { pageInfo: PageInfo! }
      type Query { widgets(first: Int, after: String): WidgetConnection }
    `);
    const field = schema.getQueryType()?.getFields().widgets;
    if (!field) throw new Error("schema has no Query.widgets");
    const resolve: GraphQLFieldResolver<unknown, Context, { first?: number; after?: string }> = (src, args, ctx) =>
      widgetResolvers.Query.widgets(src, args, ctx);
    field.resolve = resolve as GraphQLFieldResolver<unknown, unknown>;

    const { ctx, list } = makeCtx();
    const res = await graphql({ schema, source: "{ widgets(first: 500) { pageInfo { hasNextPage } } }", contextValue: ctx });
    expect(res.data).toEqual({ widgets: null });
    expect(res.errors?.[0]?.extensions?.code).toBe("VALIDATION_FAILED");
    expect(res.errors?.[0]?.extensions?.details).toEqual([
      { field: "first", code: "out_of_range", message: "Must be from 1 to 100." },
    ]);
    expect(res.errors?.[0]?.path).toEqual(["widgets"]);
    expect(list).not.toHaveBeenCalled();

    const ok = await graphql({ schema, source: "{ widgets(first: 5) { pageInfo { hasNextPage } } }", contextValue: ctx });
    expect(ok.errors).toBeUndefined();
    expect(list).toHaveBeenCalledWith("tenant-a", 5, undefined, undefined);
  });
});
