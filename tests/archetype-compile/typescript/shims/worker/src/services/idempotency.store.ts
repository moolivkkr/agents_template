// HARNESS STUB: project idempotency store the worker archetype's EmailSendHandler depends on.
export interface IdempotencyStore {
  isProcessed(key: string): Promise<boolean>;
  markProcessed(key: string, ttlMs: number): Promise<void>;
}
