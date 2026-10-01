// HARNESS STUB: the widget service frameworks/fastify.md decorates the instance with. In memory, so the
// inject() tests run without a database; tenant-scoped like the real one (another tenant's id is "not found").
import { randomUUID } from "node:crypto";
import type { PrismaClient } from "@prisma/client";

export interface Widget {
  id: string;
  tenantId: string;
  createdBy: string;
  name: string;
  description: string;
  status: "active" | "draft";
  createdAt: string;
}

export class WidgetService {
  private readonly rows = new Map<string, Widget>();

  constructor(private readonly db: PrismaClient) {}

  async create(
    tenantId: string,
    userId: string,
    body: { name: string; description?: string; status?: "active" | "draft" },
  ): Promise<Widget> {
    const widget: Widget = {
      id: randomUUID(),
      tenantId,
      createdBy: userId,
      name: body.name,
      description: body.description ?? "",
      status: body.status ?? "active",
      createdAt: new Date().toISOString(),
    };
    this.rows.set(widget.id, widget);
    return widget;
  }

  async get(tenantId: string, id: string): Promise<Widget | null> {
    const widget = this.rows.get(id);
    return widget && widget.tenantId === tenantId ? widget : null;
  }

  async list(
    tenantId: string,
    q: { cursor?: string | undefined; limit: number; sortBy: string; sortDir: "asc" | "desc" },
  ): Promise<{ items: Widget[]; nextCursor: string | null }> {
    const items = [...this.rows.values()].filter((w) => w.tenantId === tenantId).slice(0, q.limit);
    return { items, nextCursor: null };
  }

  async softDelete(tenantId: string, id: string): Promise<void> {
    if (this.rows.get(id)?.tenantId === tenantId) this.rows.delete(id);
  }
}
