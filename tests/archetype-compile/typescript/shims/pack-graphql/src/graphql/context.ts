// HARNESS STUB: the per-request GraphQL context (tenant and user from the verified token; fresh loaders).
import type { createLoaders } from "./loaders";
import type { CreateWidgetInput, Widget, WidgetFilter } from "./types";

export interface Context {
  tenantId: string;
  userId: string;
  loaders: ReturnType<typeof createLoaders>;
  widgetService: {
    get(tenantId: string, id: string): Promise<Widget | null>;
    list(tenantId: string, first: number, after: string | undefined, filter: WidgetFilter | undefined): Promise<{
      edges: { cursor: string; node: Widget }[];
      pageInfo: { hasNextPage: boolean; endCursor: string | null };
    }>;
    create(tenantId: string, userId: string, input: CreateWidgetInput): Promise<Widget>;
  };
}
