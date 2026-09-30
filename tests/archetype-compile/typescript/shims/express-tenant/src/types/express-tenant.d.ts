// HARNESS STUB: the project's Express Request augmentation. The auth/request-context middleware sets
// req.tenantId from the verified token (observability-typescript.md §Child Loggers).
declare global {
  namespace Express {
    interface Request {
      tenantId: string;
    }
  }
}

export {};
