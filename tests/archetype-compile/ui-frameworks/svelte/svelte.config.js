// Harness config: a plain SvelteKit app (adapter-node, SSR on), what frameworks/svelte.md assumes.
import adapter from "@sveltejs/adapter-node"
import { vitePreprocess } from "@sveltejs/vite-plugin-svelte"

export default {
  preprocess: vitePreprocess(),
  kit: { adapter: adapter() },
}
