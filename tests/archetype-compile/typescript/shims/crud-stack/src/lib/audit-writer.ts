// HARNESS STUB (not from the archetypes): the project's IAuditWriter implementation that
// crud-service-typescript.md's composition-root.ts constructs. Only its shape matters here.
import type { PrismaClient } from "@prisma/client";
import type { IAuditWriter } from "./audit.interface";
import type { AuditEntry } from "../domain/entity";

export class AuditWriter implements IAuditWriter {
  constructor(private readonly prisma: PrismaClient) {}

  async write(entry: AuditEntry): Promise<void> {
    void this.prisma;
    void entry;
  }
}
