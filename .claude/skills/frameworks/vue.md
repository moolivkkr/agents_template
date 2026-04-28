# Vue 3 Composition API patterns for reactive, maintainable UIs.

## Component Structure (script setup)
```vue
<script setup lang="ts">
import { ref, computed } from "vue"
import type { User } from "@/types"

const props = defineProps<{ userId: string }>()
const emit = defineEmits<{ updated: [user: User] }>()

const name = ref("")
const isValid = computed(() => name.value.length > 0)

async function handleSubmit() {
    const user = await updateUser(props.userId, { name: name.value })
    emit("updated", user)
}
</script>
```
- `<script setup>` always — concise, better type inference
- `defineProps` and `defineEmits` with TypeScript generics

## Reactivity
```typescript
// Primitive values: ref()
const count = ref(0)
count.value++

// Objects: reactive() or ref()
const form = reactive({ name: "", email: "" })

// Derived values: computed()
const fullName = computed(() => `${firstName.value} ${lastName.value}`)

// Side effects: watchEffect or watch
watchEffect(() => console.log(count.value))  // runs immediately + on change
watch(userId, (newId) => fetchUser(newId))   // explicit source
```

## State Management: Pinia
```typescript
// stores/users.ts
export const useUsersStore = defineStore("users", () => {
    const users = ref<User[]>([])
    async function fetchAll() {
        users.value = await api.getUsers()
    }
    return { users, fetchAll }
})

// In component
const store = useUsersStore()
await store.fetchAll()
```

## Composables (custom hooks equivalent)
```typescript
// composables/useUser.ts
export function useUser(userId: Ref<string>) {
    const user = ref<User | null>(null)
    const loading = ref(false)

    watch(userId, async (id) => {
        loading.value = true
        user.value = await api.getUser(id)
        loading.value = false
    }, { immediate: true })

    return { user, loading }
}
```

## Rules
- `Ref<T>` in type annotations; `.value` in code (Vue knows from `<template>`)
- Named routes always — never string paths in `router.push()`
- `v-if` over `v-show` unless toggling frequently (performance)
- `defineComponent` only needed when not using `<script setup>`
- Avoid direct DOM manipulation — use template refs if absolutely needed
