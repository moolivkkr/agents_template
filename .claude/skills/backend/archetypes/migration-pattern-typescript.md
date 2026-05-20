---
skill: migration-pattern-typescript
description: TypeScript migration archetype — Prisma migrate (dev/deploy), schema definition, seed scripts, custom SQL, multi-tenant; Drizzle kit (generate/push/migrate), TypeScript schemas, seeds
version: "1.0"
tags:
  - typescript
  - prisma
  - drizzle
  - migration
  - postgres
  - archetype
  - backend
---

# Migration Pattern Archetype — TypeScript

> **Canonical reference**: This is the TypeScript counterpart to `backend/archetypes/migration-pattern.md` (Go). Both produce identical database schemas. The Go archetype covers raw SQL migrations and golang-migrate; this covers Prisma and Drizzle ORM migration tooling.

Complete TypeScript migration templates for Prisma and Drizzle. Every generated TypeScript migration MUST follow this pattern.

---

# Prisma Section

## Prisma Schema Definition

```prisma
// prisma/schema.prisma

generator client {
  provider = "prisma-client-js"
  // Enable preview features as needed:
  // previewFeatures = ["postgresqlExtensions", "multiSchema"]
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
  // For multi-schema support:
  // schemas  = ["public", "tenant"]
}

// =============================================================================
// Core Entity: Widget
// =============================================================================

model Widget {
  id          String    @id @default(uuid()) @db.Uuid
  tenantId    String    @map("tenant_id") @db.Uuid
  name        String    @db.VarChar(255)
  description String    @default("") @db.VarChar(2000)
  status      String    @default("active") @db.VarChar(50)
  priority    Int       @default(0)
  config      Json      @default("{}")

  createdAt   DateTime  @default(now()) @map("created_at")
  updatedAt   DateTime  @updatedAt @map("updated_at")
  deletedAt   DateTime? @map("deleted_at")
  createdBy   String    @map("created_by") @db.Uuid
  updatedBy   String    @map("updated_by") @db.Uuid
  version     Int       @default(1)

  // Relations
  components  Component[]
  tenant      Tenant     @relation(fields: [tenantId], references: [id], onDelete: Cascade)

  // Indexes — match Go archetype exactly
  @@unique([tenantId, name], map: "widgets_tenant_name_unique")
  @@index([tenantId, createdAt(sort: Desc)])
  @@index([tenantId, status])
  @@index([updatedAt(sort: Desc)])
  @@map("widgets")
}

model Component {
  id        String   @id @default(uuid()) @db.Uuid
  widgetId  String   @map("widget_id") @db.Uuid
  tenantId  String   @map("tenant_id") @db.Uuid
  name      String   @db.VarChar(255)
  type      String   @db.VarChar(100)
  createdBy String   @map("created_by") @db.Uuid
  updatedBy String   @map("updated_by") @db.Uuid
  createdAt DateTime @default(now()) @map("created_at")
  updatedAt DateTime @updatedAt @map("updated_at")

  widget Widget @relation(fields: [widgetId], references: [id], onDelete: Cascade)

  @@index([widgetId])
  @@map("components")
}

model Tenant {
  id        String   @id @default(uuid()) @db.Uuid
  name      String   @db.VarChar(255)
  slug      String   @unique @db.VarChar(100)
  createdAt DateTime @default(now()) @map("created_at")
  updatedAt DateTime @updatedAt @map("updated_at")

  widgets Widget[]

  @@map("tenants")
}

// =============================================================================
// Enum alternative: Use string fields with CHECK constraints (see custom SQL)
// Prisma enums map to PostgreSQL ENUMs which are hard to modify.
// Prefer string fields with application-level validation.
// =============================================================================
```

## Prisma Migrate — Development Workflow

```bash
# Generate migration from schema changes (development only)
npx prisma migrate dev --name create_widgets_table

# This creates:
# prisma/migrations/
#   20260115100000_create_widgets_table/
#     migration.sql    <- auto-generated SQL

# Apply pending migrations to dev database
npx prisma migrate dev

# Reset dev database (drops + recreates + re-migrates + re-seeds)
npx prisma migrate reset

# View migration status
npx prisma migrate status

# Generate Prisma Client after schema changes
npx prisma generate
```

## Prisma Migrate — Production Deployment

```bash
# Apply pending migrations in production (no interactive prompts)
npx prisma migrate deploy

# This ONLY applies pending migrations — never generates new ones.
# Safe for CI/CD pipelines.
```

```typescript
// src/db/migrate.ts — Programmatic migration runner for production

import { exec } from "node:child_process";
import { promisify } from "node:util";

const execAsync = promisify(exec);

/**
 * Run Prisma migrations programmatically.
 * Use in deployment scripts or application startup.
 */
export async function runMigrations(): Promise<void> {
  try {
    const { stdout, stderr } = await execAsync("npx prisma migrate deploy");
    console.log("Migration output:", stdout);
    if (stderr) console.warn("Migration warnings:", stderr);
  } catch (error) {
    console.error("Migration failed:", error);
    throw error;
  }
}

/**
 * Check migration status — useful for health checks.
 */
export async function checkMigrationStatus(): Promise<boolean> {
  try {
    const { stdout } = await execAsync("npx prisma migrate status");
    return !stdout.includes("have not yet been applied");
  } catch {
    return false;
  }
}
```

## Prisma Custom Migration SQL

```sql
-- prisma/migrations/20260115100100_add_rls_policies/migration.sql
--
-- Prisma does not auto-generate RLS policies, triggers, or partial indexes.
-- Add them as custom SQL in a blank migration.
--
-- Create with: npx prisma migrate dev --create-only --name add_rls_policies
-- Then edit the generated migration.sql file before applying.

-- Row-Level Security
ALTER TABLE widgets ENABLE ROW LEVEL SECURITY;
ALTER TABLE widgets FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON widgets
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Partial unique index (soft delete aware)
DROP INDEX IF EXISTS widgets_tenant_name_unique;
CREATE UNIQUE INDEX widgets_tenant_name_unique
    ON widgets (tenant_id, lower(name))
    WHERE deleted_at IS NULL;

-- Auto-update updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_widgets_updated_at
    BEFORE UPDATE ON widgets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Table comments
COMMENT ON TABLE widgets IS 'Core widget entities — multi-tenant, soft-deletable';
COMMENT ON COLUMN widgets.tenant_id IS 'Owning tenant — enforced by RLS policy';
COMMENT ON COLUMN widgets.deleted_at IS 'Soft delete timestamp — NULL means active';
COMMENT ON COLUMN widgets.version IS 'Optimistic lock counter — increment on every update';
```

## Prisma Seed Script

```typescript
// prisma/seed.ts
//
// Run with: npx prisma db seed
// Configure in package.json:
// "prisma": { "seed": "tsx prisma/seed.ts" }

import { PrismaClient } from "@prisma/client";
import { randomUUID } from "node:crypto";

const prisma = new PrismaClient();

async function main(): Promise<void> {
  console.log("Seeding database...");

  // 1. Create default tenant
  const tenant = await prisma.tenant.upsert({
    where: { slug: "default" },
    update: {},
    create: {
      id: "00000000-0000-4000-a000-000000000001",
      name: "Default Organization",
      slug: "default",
    },
  });

  console.log(`Tenant: ${tenant.name} (${tenant.id})`);

  // 2. Create seed widgets
  const widgets = [
    { name: "Dashboard Widget", description: "Main dashboard component", status: "active" },
    { name: "Analytics Widget", description: "Data visualization panel", status: "active" },
    { name: "Legacy Widget", description: "Deprecated — scheduled for removal", status: "archived" },
  ];

  const adminUserId = "00000000-0000-4000-a000-000000000099";

  for (const w of widgets) {
    await prisma.widget.upsert({
      where: {
        tenantId_name: { tenantId: tenant.id, name: w.name },
      },
      update: {},
      create: {
        id: randomUUID(),
        tenantId: tenant.id,
        name: w.name,
        description: w.description,
        status: w.status,
        createdBy: adminUserId,
        updatedBy: adminUserId,
        version: 1,
      },
    });
    console.log(`  Widget: ${w.name}`);
  }

  console.log("Seeding complete.");
}

main()
  .catch((e) => {
    console.error("Seed failed:", e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
```

## Prisma Multi-Schema / Multi-Tenant

```prisma
// prisma/schema.prisma — Multi-schema setup (preview feature)

generator client {
  provider        = "prisma-client-js"
  previewFeatures = ["multiSchema"]
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
  schemas  = ["public", "tenant_data"]
}

// Public schema — shared lookup tables
model Tenant {
  id   String @id @default(uuid()) @db.Uuid
  name String @db.VarChar(255)
  slug String @unique @db.VarChar(100)

  @@map("tenants")
  @@schema("public")
}

// Tenant data schema — partitioned or RLS-protected
model Widget {
  id       String @id @default(uuid()) @db.Uuid
  tenantId String @map("tenant_id") @db.Uuid
  name     String @db.VarChar(255)
  // ... other fields

  @@map("widgets")
  @@schema("tenant_data")
}
```

---

# Drizzle Section

## Drizzle Schema Definition

```typescript
// src/db/schema.ts

import {
  pgTable,
  uuid,
  varchar,
  text,
  integer,
  timestamp,
  json,
  index,
  uniqueIndex,
} from "drizzle-orm/pg-core";
import { relations } from "drizzle-orm";

// =============================================================================
// Core Entity: Widget
// =============================================================================

export const widgets = pgTable(
  "widgets",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    name: varchar("name", { length: 255 }).notNull(),
    description: varchar("description", { length: 2000 }).default("").notNull(),
    status: varchar("status", { length: 50 }).default("active").notNull(),
    priority: integer("priority").default(0).notNull(),
    config: json("config").default({}).notNull(),

    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
    deletedAt: timestamp("deleted_at", { withTimezone: true }),
    createdBy: uuid("created_by").notNull(),
    updatedBy: uuid("updated_by").notNull(),
    version: integer("version").default(1).notNull(),
  },
  (table) => ({
    tenantCreatedIdx: index("widgets_tenant_created_idx").on(table.tenantId, table.createdAt),
    tenantStatusIdx: index("widgets_tenant_status_idx").on(table.tenantId, table.status),
    tenantNameUnique: uniqueIndex("widgets_tenant_name_unique").on(table.tenantId, table.name),
    updatedAtIdx: index("widgets_updated_at_idx").on(table.updatedAt),
  }),
);

export const components = pgTable(
  "components",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    widgetId: uuid("widget_id").notNull().references(() => widgets.id, { onDelete: "cascade" }),
    tenantId: uuid("tenant_id").notNull(),
    name: varchar("name", { length: 255 }).notNull(),
    type: varchar("type", { length: 100 }).notNull(),
    createdBy: uuid("created_by").notNull(),
    updatedBy: uuid("updated_by").notNull(),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (table) => ({
    widgetIdx: index("components_widget_idx").on(table.widgetId),
  }),
);

export const tenants = pgTable("tenants", {
  id: uuid("id").primaryKey().defaultRandom(),
  name: varchar("name", { length: 255 }).notNull(),
  slug: varchar("slug", { length: 100 }).notNull().unique(),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
});

// =============================================================================
// Relations
// =============================================================================

export const widgetRelations = relations(widgets, ({ many, one }) => ({
  components: many(components),
  tenant: one(tenants, { fields: [widgets.tenantId], references: [tenants.id] }),
}));

export const componentRelations = relations(components, ({ one }) => ({
  widget: one(widgets, { fields: [components.widgetId], references: [widgets.id] }),
}));

export const tenantRelations = relations(tenants, ({ many }) => ({
  widgets: many(widgets),
}));

// =============================================================================
// Type Inference Helpers
// =============================================================================

export type WidgetInsert = typeof widgets.$inferInsert;
export type WidgetSelect = typeof widgets.$inferSelect;
export type ComponentInsert = typeof components.$inferInsert;
export type ComponentSelect = typeof components.$inferSelect;
export type TenantInsert = typeof tenants.$inferInsert;
export type TenantSelect = typeof tenants.$inferSelect;
```

## Drizzle Kit Configuration

```typescript
// drizzle.config.ts

import { defineConfig } from "drizzle-kit";

export default defineConfig({
  // Schema files — Drizzle reads TypeScript directly
  schema: "./src/db/schema.ts",

  // Output directory for generated migration SQL files
  out: "./drizzle",

  // Database driver
  dialect: "postgresql",

  // Connection for introspection and push
  dbCredentials: {
    url: process.env.DATABASE_URL!,
  },

  // Verbose SQL output during generation
  verbose: true,

  // Strict mode — fails on ambiguous changes
  strict: true,
});
```

## Drizzle Kit — Development Workflow

```bash
# Generate SQL migration from schema changes
npx drizzle-kit generate

# This creates:
# drizzle/
#   0000_create_widgets.sql
#   0001_add_components.sql
#   meta/
#     _journal.json

# Apply migrations to database (production-safe)
npx drizzle-kit migrate

# Push schema directly to database (development only — no migration file)
# WARNING: Not safe for production — use migrate instead
npx drizzle-kit push

# Pull existing database schema into Drizzle TypeScript schema
npx drizzle-kit introspect

# Open Drizzle Studio (visual database browser)
npx drizzle-kit studio

# View migration status
npx drizzle-kit check
```

## Drizzle Migrate — Programmatic Runner

```typescript
// src/db/migrate.ts

import postgres from "postgres";
import { drizzle } from "drizzle-orm/postgres-js";
import { migrate } from "drizzle-orm/postgres-js/migrator";

/**
 * Run Drizzle migrations programmatically.
 * Use in deployment scripts or application startup.
 */
export async function runMigrations(connectionString: string): Promise<void> {
  // Use a dedicated connection for migrations (not the pool)
  const migrationClient = postgres(connectionString, { max: 1 });
  const db = drizzle(migrationClient);

  console.log("Running migrations...");

  await migrate(db, {
    migrationsFolder: "./drizzle",
    migrationsTable: "drizzle_migrations",
  });

  console.log("Migrations complete.");
  await migrationClient.end();
}

// Run directly: tsx src/db/migrate.ts
if (import.meta.url === `file://${process.argv[1]}`) {
  const url = process.env.DATABASE_URL;
  if (!url) {
    console.error("DATABASE_URL is required");
    process.exit(1);
  }
  runMigrations(url)
    .then(() => process.exit(0))
    .catch((err) => {
      console.error("Migration failed:", err);
      process.exit(1);
    });
}
```

## Drizzle Custom SQL Migrations

```sql
-- drizzle/0002_add_rls_policies.sql
--
-- Custom SQL that Drizzle Kit cannot auto-generate.
-- Create this file manually and it will be included in the migration chain.

-- Row-Level Security
ALTER TABLE widgets ENABLE ROW LEVEL SECURITY;
ALTER TABLE widgets FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON widgets
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Auto-update trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_widgets_updated_at
    BEFORE UPDATE ON widgets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

## Drizzle Seed Script

```typescript
// src/db/seed.ts
//
// Run with: tsx src/db/seed.ts

import postgres from "postgres";
import { drizzle } from "drizzle-orm/postgres-js";
import { eq } from "drizzle-orm";
import { randomUUID } from "node:crypto";
import { tenants, widgets } from "./schema";

async function seed(): Promise<void> {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error("DATABASE_URL is required");
  }

  const client = postgres(connectionString, { max: 1 });
  const db = drizzle(client);

  console.log("Seeding database...");

  // 1. Upsert default tenant
  const tenantId = "00000000-0000-4000-a000-000000000001";
  const [tenant] = await db
    .insert(tenants)
    .values({
      id: tenantId,
      name: "Default Organization",
      slug: "default",
    })
    .onConflictDoNothing({ target: tenants.slug })
    .returning();

  const effectiveTenantId = tenant?.id ?? tenantId;
  console.log(`Tenant: ${effectiveTenantId}`);

  // 2. Seed widgets
  const adminUserId = "00000000-0000-4000-a000-000000000099";
  const seedWidgets = [
    { name: "Dashboard Widget", description: "Main dashboard component", status: "active" },
    { name: "Analytics Widget", description: "Data visualization panel", status: "active" },
    { name: "Legacy Widget", description: "Deprecated — scheduled for removal", status: "archived" },
  ];

  for (const w of seedWidgets) {
    await db
      .insert(widgets)
      .values({
        id: randomUUID(),
        tenantId: effectiveTenantId,
        name: w.name,
        description: w.description,
        status: w.status,
        createdBy: adminUserId,
        updatedBy: adminUserId,
        version: 1,
      })
      .onConflictDoNothing();
    console.log(`  Widget: ${w.name}`);
  }

  console.log("Seeding complete.");
  await client.end();
}

seed().catch((err) => {
  console.error("Seed failed:", err);
  process.exit(1);
});
```

---

## Push vs Migrate — When to Use Which

| Command | Environment | What It Does | Safe? |
|---------|------------|--------------|-------|
| `drizzle-kit push` | **Development only** | Syncs schema directly, no migration file | No migration history |
| `drizzle-kit generate` + `migrate` | **All environments** | Creates SQL file, then applies it | Yes — versioned, auditable |
| `prisma migrate dev` | **Development only** | Generates + applies migration | Development only |
| `prisma migrate deploy` | **Production** | Applies pending migrations | Yes — versioned, auditable |

**Rule**: Always use `generate` + `migrate` (Drizzle) or `migrate deploy` (Prisma) in staging and production. Never use `push` or `migrate dev` in production.

---

## Package.json Scripts

```json
{
  "scripts": {
    "db:generate": "npx prisma generate",
    "db:migrate:dev": "npx prisma migrate dev",
    "db:migrate:deploy": "npx prisma migrate deploy",
    "db:migrate:reset": "npx prisma migrate reset",
    "db:seed": "tsx prisma/seed.ts",
    "db:studio": "npx prisma studio",

    "drizzle:generate": "npx drizzle-kit generate",
    "drizzle:migrate": "npx drizzle-kit migrate",
    "drizzle:push": "npx drizzle-kit push",
    "drizzle:studio": "npx drizzle-kit studio",
    "drizzle:seed": "tsx src/db/seed.ts"
  },
  "prisma": {
    "seed": "tsx prisma/seed.ts"
  }
}
```

---

## Critical Rules

- Every table MUST have `tenant_id`, `deleted_at`, `version`, `created_at`, `updated_at` columns
- Prisma `@updatedAt` auto-updates `updated_at` — but add a trigger for direct SQL updates
- Drizzle schemas define columns in TypeScript — no separate SDL file
- Unique indexes MUST be scoped to tenant: `(tenant_id, column)` not just `(column)`
- Use `onConflictDoNothing()` (Drizzle) or `upsert()` (Prisma) in seeds for idempotency
- Custom SQL (RLS, triggers, partial indexes) MUST be added as manual migration files
- Never use `prisma migrate dev` or `drizzle-kit push` in production
- Seed data MUST be separate from schema migrations
- Migration files MUST be committed to version control
- Drizzle `generate` creates SQL files under `drizzle/` — review before applying
- Prisma `migrate dev --create-only` generates migration SQL without applying — use for custom edits
- Foreign keys MUST specify `onDelete` behavior explicitly (Cascade, SetNull, Restrict)
- JSONB columns MUST have a GIN index if they will be queried
- `strict: true` in drizzle.config.ts prevents ambiguous schema changes
