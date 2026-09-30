// HARNESS STUB: the project's Drizzle tables that observability-typescript.md's drizzle.ts queries.
import { integer, pgTable, timestamp, uuid, varchar } from "drizzle-orm/pg-core";

export const orders = pgTable("orders", {
  id: uuid("id").primaryKey().defaultRandom(),
  tenantId: uuid("tenant_id").notNull(),
  status: varchar("status", { length: 50 }).notNull(),
  total: integer("total").notNull(),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
});
