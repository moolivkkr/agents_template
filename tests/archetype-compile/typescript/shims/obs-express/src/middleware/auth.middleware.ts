// HARNESS STUB: the auth middleware observability-typescript.md's main.ts mounts. It verifies the
// bearer token and sets req.auth = { tenantId, userId } from the claims.
import type { NextFunction, Request, Response } from "express";

export declare function authMiddleware(req: Request, res: Response, next: NextFunction): void;
