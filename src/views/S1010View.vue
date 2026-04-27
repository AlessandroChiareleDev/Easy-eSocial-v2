<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { RouterLink } from "vue-router";
import { api } from "@/services/api";

interface Rubrica {
  id: number | string;
  codigo?: string;
  descricao?: string;
  nome?: string;
  natureza_codigo?: string;
  natureza_nome?: string;
  problema?: string;
  status?: string;
  empresa_id?: number | string;
}

interface RubricasResponse {
  total?: number;
  rubrics?: Rubrica[];
  rubricas?: Rubrica[];
  data?: Rubrica[];
}

interface Progresso {
  total?: number;
  corrigidas?: number;
  pendentes?: number;
  pct?: number;
  applied?: number;
}

const items = ref<Rubrica[]>([]);
const total = ref<number | null>(null);
const progress = ref<Progresso | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);

const page = ref(1);
const limit = ref(50);
const apenasPendentes = ref(true);
const filterText = ref("");

const totalPages = computed(() =>
  total.value !== null && limit.value > 0
    ? Math.max(1, Math.ceil(total.value / limit.value))
    : 1,
);

const filtered = computed(() => {
  const q = filterText.value.trim().toLowerCase();
  if (!q) return items.value;
  return items.value.filter((it) =>
    JSON.stringify(it).toLowerCase().includes(q),
  );
});

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const offset = (page.value - 1) * limit.value;
    const params = new URLSearchParams({
      limit: String(limit.value),
      offset: String(offset),
      apenaPendentes: apenasPendentes.value ? "true" : "false",
    });
    const [res, prog] = await Promise.all([
      api.get<RubricasResponse>(`/rubricas/com-problemas?${params}`),
      api.get<Progresso>("/rubricas/progresso").catch(() => null),
    ]);
    items.value = res.rubrics ?? res.rubricas ?? res.data ?? [];
    total.value = res.total ?? items.value.length;
    if (prog) progress.value = prog;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Falha ao carregar";
    items.value = [];
  } finally {
    loading.value = false;
  }
}

function fmt(n: number | null | undefined): string {
  return n === null || n === undefined ? "—" : n.toLocaleString("pt-BR");
}

watch([page, limit, apenasPendentes], load);
onMounted(load);
</script>

<template>
  <main class="dt-page">
    <RouterLink to="/" class="dt-back">← Painel</RouterLink>

    <header class="dt-head">
      <div>
        <h1>eSocial S-1010</h1>
        <p class="sub">
          Rubricas com naturezas inválidas · validação · envio webservice.
        </p>
      </div>
      <div class="dt-counts">
        <span class="kv">
          <span class="lbl">com problema</span>
          <span class="num gg-glow">{{ fmt(total) }}</span>
        </span>
        <span class="kv" v-if="progress?.corrigidas != null">
          <span class="lbl">corrigidas</span>
          <span class="num">{{ fmt(progress.corrigidas) }}</span>
        </span>
        <span class="kv" v-if="progress?.pct != null">
          <span class="lbl">progresso</span>
          <span class="num">{{ progress.pct.toFixed(1) }}%</span>
        </span>
      </div>
    </header>

    <div class="dt-toolbar liquid-glass">
      <input
        v-model="filterText"
        type="search"
        placeholder="filtrar (código, descrição, natureza…)"
        class="dt-search"
      />
      <div class="dt-pager">
        <label
          class="dt-info"
          style="display: inline-flex; align-items: center; gap: 6px"
        >
          <input v-model="apenasPendentes" type="checkbox" />
          apenas pendentes
        </label>
        <button class="dt-btn" :disabled="page <= 1 || loading" @click="page--">
          ←
        </button>
        <span class="dt-info">{{ page }} / {{ totalPages }}</span>
        <button
          class="dt-btn"
          :disabled="page >= totalPages || loading"
          @click="page++"
        >
          →
        </button>
        <button class="dt-btn dt-btn--accent" :disabled="loading" @click="load">
          {{ loading ? "…" : "↻" }}
        </button>
      </div>
    </div>

    <div v-if="error" class="dt-err liquid-glass" role="alert">
      <strong>backend:</strong> {{ error }}
    </div>

    <div class="dt-table-wrap liquid-glass">
      <table v-if="filtered.length > 0" class="dt-table">
        <thead>
          <tr>
            <th>código</th>
            <th>descrição</th>
            <th>natureza atual</th>
            <th>nome natureza</th>
            <th>problema</th>
            <th>status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="it in filtered" :key="it.id">
            <td class="mono">{{ it.codigo ?? "—" }}</td>
            <td>{{ it.descricao ?? it.nome ?? "—" }}</td>
            <td class="mono">{{ it.natureza_codigo ?? "—" }}</td>
            <td>{{ it.natureza_nome ?? "—" }}</td>
            <td>
              <span class="dt-tag dt-tag--warn">{{ it.problema ?? "—" }}</span>
            </td>
            <td>
              <span
                class="dt-tag"
                :class="{ 'dt-tag--neutral': it.status !== 'pending' }"
                >{{ it.status ?? "—" }}</span
              >
            </td>
          </tr>
        </tbody>
      </table>

      <div v-else-if="loading" class="dt-empty">
        <span class="dot">●</span> carregando…
      </div>
      <div v-else class="dt-empty">sem rubricas com problema · tudo limpo.</div>
    </div>
  </main>
</template>
