// Harness config: SvelteKit + Vitest (jsdom) + Testing Library's Svelte plugin.
import { sveltekit } from "@sveltejs/kit/vite"
import { svelteTesting } from "@testing-library/svelte/vite"
import { defineConfig } from "vitest/config"

export default defineConfig({
  plugins: [sveltekit(), svelteTesting()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/lib/test/setup.ts"],
    include: ["src/**/*.test.ts"],
    allowOnly: false,
    retry: 0,
  },
})
