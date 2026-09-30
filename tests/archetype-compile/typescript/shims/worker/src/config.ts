// HARNESS STUB: the project's env config loader the worker archetype's main.ts imports.
export interface WorkerEnvConfig {
  redisUrl: string;
  workerConcurrency: number;
  jobTimeoutMs: number;
}

export declare function loadConfig(): WorkerEnvConfig;
