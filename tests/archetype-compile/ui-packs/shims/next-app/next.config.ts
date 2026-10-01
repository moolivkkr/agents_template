// HARNESS: Next.js config for the ui-packs Next app unit. `next build` runs its own TypeScript pass (TS 7)
// after the harness's tsc, and validates "use client" / "use server" boundaries while compiling.
import type { NextConfig } from "next";
import path from "node:path";

const config: NextConfig = {
  // node_modules live two levels up (tests/archetype-compile/ui-packs/web), beside the lockfile.
  turbopack: { root: path.resolve(process.cwd(), "../..") },
};

export default config;
