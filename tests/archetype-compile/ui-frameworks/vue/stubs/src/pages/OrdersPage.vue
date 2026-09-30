<!-- HARNESS STUB: a page hosting vue.md's OrderList, with the <h1 tabindex="-1"> focus target. -->
<script setup lang="ts">
import OrderList from "@/components/OrderList.vue"
import { t } from "@/i18n"
</script>

<template>
  <h1 tabindex="-1">{{ t("orders.title") }}</h1>
  <OrderList @create="$router.push({ name: 'order-new' })" />
</template>
