// HARNESS STUB: the project's Express Request augmentation that the core/ and languages/ samples assume — the
// fields backend/archetypes/observability-typescript.md declares: the user from the verified token (set by
// the auth middleware), a validated request id, and a per-request child logger.
import type { Logger } from "pino";

declare global {
  namespace Express {
    interface Request {
      id: string;
      user?: { id: string; tenantId: string; roles: string[]; permissions: string[] };
      logger: Logger;
    }
  }
}

export {};
