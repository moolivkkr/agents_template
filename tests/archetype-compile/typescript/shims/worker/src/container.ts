// HARNESS STUB: the project's composition root the worker archetype's main.ts imports.
import type { EmailService } from "./services/email.service";
import type { IdempotencyStore } from "./services/idempotency.store";
import type { ReportService } from "./handlers/report-generate.handler";

export declare const emailService: EmailService;
export declare const idempotencyStore: IdempotencyStore;
export declare const reportService: ReportService;
