<script setup lang="ts">
import { RouterView } from 'vue-router';
</script>

<template>
  <!-- Aura Blush Frost difusa atrás de tudo (contraste pra não ficar 90% verde) -->
  <div class="blush-aura" aria-hidden="true"></div>
  <div class="blush-aura blush-aura--secondary" aria-hidden="true"></div>

  <RouterView />
</template>
