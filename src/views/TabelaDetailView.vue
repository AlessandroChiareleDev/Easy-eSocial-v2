<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { api } from "@/services/api";

const route = useRoute();
const tableName = computed(() => String(route.params.nome ?? ""));

const columns = ref<string[]>([]);
const rows = ref<Record<string, unknown>[]>([]);
const total = ref<number | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);

const page = ref(1);
const limit = ref(50);
const filterText = ref("");

const totalPages = computed(() =>
  total.value !== null && limit.value > 0
    ? Math.max(1, Math.ceil(total.value / limit.value))
    : 1,
);

const visibleColumns = computed(() => columns.value.slice(0, 12));

const filtered = computed(() => {
  const q = filterText.value.trim().toLowerCase();
  if (!q) return rows.value;
  return rows.value.filter((r) => JSON.stringify(r).toLowerCase().includes(q));
});

async function loadColumns() {
  if (!tableName.value) return;
  try {
    const res = await api.get<{ columns?: string[] } | string[]>(
      `/tables/${encodeURIComponent(tableName.value)}/columns`,
    );
    if (Array.isArray(res)) columns.value = res;
    else columns.value = res.columns ?? [];
  } catch {
    columns.value = [];
  }
}

async function loadRows() {
  if (!tableName.value) return;
  loading.value = true;
  error.value = null;
  try {
    const offset = (page.value - 1) * limit.value;
    const res = await api.get<{
      data?: Record<string, unknown>[];
      total?: number;
    }>(
      `/tables/${encodeURIComponent(tableName.value)}?limit=${limit.value}&offset=${offset}`,
    );
    rows.value = res.data ?? [];
    total.value = res.total ?? rows.value.length;
    if (columns.value.length === 0 && rows.value[0]) {
      columns.value = Object.keys(rows.value[0]);
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Falha ao carregar dados";
    rows.value = [];
  } finally {
    loading.value = false;
  }
}

function fmtCell(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  if (typeof v === "boolean") return v ? "✓" : "✗";
  const s = String(v);
  return s.length > 80 ? s.slice(0, 77) + "…" : s;
}

watch([page, limit, tableName], async () => {
  await loadColumns();
  await loadRows();
});

onMounted(async () => {
  await loadColumns();
  await loadRows();
});
</script>

<template>
  <main class="dt-page">
    <RouterLink to="/tabelas" class="dt-back">← Tabelas</RouterLink>

    <header class="dt-head">
      <div>
        <h1>{{ tableName }}</h1>
        <p class="sub">
          {{ columns.length }} colunas
          <span v-if="visibleColumns.length < columns.length">
            (mostrando primeiras {{ visibleColumns.length }})</span
          >
          · linhas vindas de
          <code>/api/tables/{{ tableName }}</code>
        </p>
      </div>
      <div class="dt-counts">
        <span class="kv">
          <span class="lbl">total</span>
          <span class="num gg-glow">{{
            total === null ? "—" : total.toLocaleString("pt-BR")
          }}</span>
        </span>
      </div>
    </header>

    <div class="dt-toolbar liquid-glass">
      <input
        v-model="filterText"
        type="search"
        placeholder="filtrar nesta página…"
        class="dt-search"
      />
      <div class="dt-pager">
        <button class="dt-btn" :disabled="page <= 1 || loading" @click="page--">
          ← anterior
        </button>
        <span class="dt-info"
          >pág {{ page }} / {{ totalPages }} · {{ rows.length }}</span
        >
        <button
          class="dt-btn"
          :disabled="page >= totalPages || loading"
          @click="page++"
        >
          próxima →
        </button>
        <button
          class="dt-btn dt-btn--accent"
          :disabled="loading"
          @click="loadRows"
        >
          {{ loading ? "carregando…" : "↻ atualizar" }}
        </button>
      </div>
    </div>

    <div v-if="error" class="dt-err liquid-glass" role="alert">
      <strong>backend indisponível:</strong> {{ error }}
    </div>

    <div class="dt-table-wrap liquid-glass">
      <table v-if="filtered.length > 0" class="dt-table">
        <thead>
          <tr>
            <th v-for="c in visibleColumns" :key="c">{{ c }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in filtered" :key="i">
            <td
              v-for="c in visibleColumns"
              :key="c"
              :title="String(r[c] ?? '')"
            >
              {{ fmtCell(r[c]) }}
            </td>
          </tr>
        </tbody>
      </table>

      <div v-else-if="loading" class="dt-empty">
        <span class="dot">●</span> carregando do backend…
      </div>
      <div v-else class="dt-empty">
        sem registros
        <span v-if="filterText">· filtro: "{{ filterText }}"</span>
      </div>
    </div>
  </main>
</template>
