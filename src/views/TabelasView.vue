<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { RouterLink } from "vue-router";
import { api } from "@/services/api";

interface TableInfo {
  name: string;
  rowCount?: number;
  count?: number;
  total?: number;
}

interface TablesResponse {
  tables?: TableInfo[];
}

const items = ref<TableInfo[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);
const filterText = ref("");

const filtered = computed(() => {
  const q = filterText.value.trim().toLowerCase();
  if (!q) return items.value;
  return items.value.filter((t) => t.name.toLowerCase().includes(q));
});

function pickCount(t: TableInfo): number | null {
  return t.rowCount ?? t.count ?? t.total ?? null;
}

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const res = await api.get<TablesResponse | TableInfo[] | string[]>(
      "/tables",
    );
    let raw: unknown[] = [];
    if (Array.isArray(res)) raw = res;
    else raw = res.tables ?? [];

    items.value = raw.map((r) =>
      typeof r === "string" ? { name: r } : (r as TableInfo),
    );
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Falha ao carregar tabelas";
    items.value = [];
  } finally {
    loading.value = false;
  }
}

function fmt(n: number | null): string {
  return n === null ? "—" : n.toLocaleString("pt-BR");
}

onMounted(load);
</script>

<template>
  <main class="dt-page">
    <RouterLink to="/" class="dt-back">← Painel</RouterLink>

    <header class="dt-head">
      <div>
        <h1>Tabelas</h1>
        <p class="sub">
          S-1000 · S-1005 · S-1010 · rubricas · lotações · estabelecimentos.
        </p>
      </div>
      <div class="dt-counts">
        <span class="kv">
          <span class="lbl">tabelas</span>
          <span class="num gg-glow">{{ fmt(items.length) }}</span>
        </span>
      </div>
    </header>

    <div class="dt-toolbar liquid-glass">
      <input
        v-model="filterText"
        type="search"
        placeholder="filtrar por nome…"
        class="dt-search"
      />
      <div class="dt-pager">
        <button class="dt-btn dt-btn--accent" :disabled="loading" @click="load">
          {{ loading ? "carregando…" : "↻ atualizar" }}
        </button>
      </div>
    </div>

    <div v-if="error" class="dt-err liquid-glass" role="alert">
      <strong>backend indisponível:</strong> {{ error }}
    </div>

    <div v-if="filtered.length > 0" class="dt-grid">
      <RouterLink
        v-for="t in filtered"
        :key="t.name"
        :to="{ name: 'tabela-detail', params: { nome: t.name } }"
        class="dt-card liquid-glass"
      >
        <span class="meta">tabela</span>
        <span class="name">{{ t.name }}</span>
        <span v-if="pickCount(t) !== null" class="count">{{
          fmt(pickCount(t))
        }}</span>
        <span v-else class="count" style="opacity: 0.4">—</span>
      </RouterLink>
    </div>

    <div v-else-if="loading" class="dt-empty liquid-glass">
      <span class="dot">●</span> carregando do backend…
    </div>
    <div v-else class="dt-empty liquid-glass">
      sem tabelas
      <span v-if="filterText">· filtro: "{{ filterText }}"</span>
    </div>
  </main>
</template>
