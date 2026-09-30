// HARNESS STUB: the main.ts wiring vue.md §5 describes in prose (compiled here so the prose stays true).
import { VueQueryPlugin } from "@tanstack/vue-query"
import { createPinia } from "pinia"
import { createApp } from "vue"
import App from "@/App.vue"
import { createQueryClient } from "@/api/query-client"
import { router } from "@/router"
import { useSession } from "@/session/session"

const app = createApp(App).use(createPinia()).use(router)
const queryClient = createQueryClient(() => {
  useSession().clear()
  void router.push({ name: "login", query: { returnTo: router.currentRoute.value.fullPath } })
})
app.use(VueQueryPlugin, { queryClient }).mount("#app")
