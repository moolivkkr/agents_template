<!-- HARNESS STUB: a project's create-order page (the router in vue.md lazy-loads it). -->
<script setup lang="ts">
import OrderForm from "@/components/OrderForm.vue"
import { t } from "@/i18n"
</script>

<template>
  <h1 tabindex="-1">{{ t("orders.form.title") }}</h1>
  <OrderForm @created="$router.push({ name: 'orders' })" />
</template>
