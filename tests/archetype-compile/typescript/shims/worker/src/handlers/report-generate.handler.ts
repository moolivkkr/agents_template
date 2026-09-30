// HARNESS STUB: a second JobHandler the worker archetype's main.ts registers.
import type { Job, JobHandler } from "../worker/types";

export interface ReportService {
  generate(tenantId: string, payload: unknown): Promise<void>;
}

export class ReportGenerateHandler implements JobHandler {
  readonly type = "report.generate";
  constructor(private readonly reports: ReportService) {}
  async handle(job: Job): Promise<void> {
    await this.reports.generate(job.tenantId, job.payload);
  }
}
