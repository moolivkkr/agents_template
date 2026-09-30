<!-- HARNESS STUB: the app shell vue.md §7 describes (skip link + <main>). -->
<script setup lang="ts">
import { t } from "@/i18n"
</script>

<template>
  <a href="#main" class="sr-only focus:not-sr-only">{{ t("a11y.skipToContent") }}</a>
  <main id="main"><RouterView /></main>
</template>
