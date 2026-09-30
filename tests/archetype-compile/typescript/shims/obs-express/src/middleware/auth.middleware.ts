// HARNESS STUB: the auth middleware observability-typescript.md's main.ts mounts. It verifies the
// bearer token and sets req.user (an AuthUser) from the claims, like auth-middleware-typescript.md.
import type { NextFunction, Request, Response } from "express";

export declare function authMiddleware(req: Request, res: Response, next: NextFunction): void;
