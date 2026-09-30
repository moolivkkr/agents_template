// HARNESS STUB: the error middleware observability-typescript.md's main.ts mounts last.
import type { NextFunction, Request, Response } from "express";

export declare function errorHandler(err: unknown, req: Request, res: Response, next: NextFunction): void;
