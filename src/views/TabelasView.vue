<script setup lang="ts">
import { RouterLink } from 'vue-router';
</script>

<template>
  <main class="page">
    <RouterLink to="/" class="back">← Painel</RouterLink>
    <h1>Tabelas</h1>
    <p class="sub">S-1000 · S-1005 · S-1010 · rubricas, lotações, estabelecimentos.</p>
    <div class="liquid-glass placeholder">
      <span>em construção — Fase 3</span>
    </div>
  </main>
</template>

<style scoped>
.page { max-width: 1180px; margin: 0 auto; padding: 56px 32px; }
.back { font-family: 'Geist Mono', ui-monospace, monospace; font-size: 12px; color: var(--text-muted); text-decoration: none; letter-spacing: 0.1em; }
.back:hover { color: var(--primary); }
h1 { font-size: 32px; font-weight: 500; letter-spacing: -0.02em; margin: 16px 0 6px; }
.sub { color: var(--text-muted); font-size: 14px; margin: 0 0 28px; }
.placeholder { padding: 60px; display: grid; place-items: center; color: var(--text-muted); font-family: 'Geist Mono', ui-monospace, monospace; font-size: 12px; letter-spacing: 0.18em; text-transform: uppercase; }
</style>
