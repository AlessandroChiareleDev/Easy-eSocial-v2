<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { RouterLink } from "vue-router";
import { api } from "@/services/api";

interface Divergencia {
  id: number | string;
  cpf?: string;
  nome?: string;
  tipo?: string;
  campo?: string;
  valor_esperado?: string | number | null;
  valor_encontrado?: string | number | null;
  status?: string;
  observacao?: string;
  criado_em?: string;
  created_at?: string;
}

interface DivergenciasResponse {
  total?: number;
  divergencias?: Divergencia[];
  data?: Divergencia[];
  items?: Divergencia[];
}

interface ResumoResponse {
  total?: number;
  totals?: number;
  pending?: number;
  corrected?: number;
  verified?: number;
  ok?: number;
  divergencias?: number;
}

const items = ref<Divergencia[]>([]);
const total = ref<number | null>(null);
const resumo = ref<ResumoResponse | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);

const page = ref(1);
const limit = ref(50);
const status = ref<string>("pending");
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
    });
    if (status.value) params.set("status", status.value);

    const [res, sum] = await Promise.all([
      api.get<DivergenciasResponse>(`/validacao/divergencias?${params}`),
      api.get<ResumoResponse>("/validacao/resumo").catch(() => null),
    ]);
    items.value = res.divergencias ?? res.data ?? res.items ?? [];
    total.value = res.total ?? items.value.length;
    if (sum) resumo.value = sum;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Falha ao carregar";
    items.value = [];
  } finally {
    loading.value = false;
  }
}

async function corrigir(id: number | string) {
  if (!confirm("Marcar como corrigida?")) return;
  try {
    await api.patch(`/validacao/${id}/corrigir`, {
      observacao: "corrigida via V2",
    });
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Falha ao corrigir";
  }
}

async function verificar(id: number | string) {
  try {
    await api.patch(`/validacao/${id}/verificar`);
    await load();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Falha ao verificar";
  }
}

function fmtVal(v: string | number | null | undefined): string {
  if (v === null || v === undefined || v === "") return "—";
  return String(v);
}
function fmtDate(it: Divergencia): string {
  const raw = it.criado_em || it.created_at;
  if (!raw) return "—";
  try {
    return new Date(raw).toLocaleString("pt-BR");
  } catch {
    return raw;
  }
}
function statusTag(s?: string): string {
  if (!s) return "dt-tag dt-tag--neutral";
  if (s === "pending") return "dt-tag dt-tag--err";
  if (s === "corrected") return "dt-tag";
  if (s === "verified") return "dt-tag";
  return "dt-tag dt-tag--neutral";
}

const pendCount = computed(
  () => resumo.value?.pending ?? resumo.value?.divergencias ?? null,
);

watch([page, limit, status], load);
onMounted(load);
</script>

<template>
  <main class="dt-page">
    <RouterLink to="/" class="dt-back">← Painel</RouterLink>

    <header class="dt-head">
      <div>
        <h1>Problemas</h1>
        <p class="sub">Erros L1 / L2 · pendências · reenvios.</p>
      </div>
      <div class="dt-counts">
        <span class="kv">
          <span class="lbl">pendentes</span>
          <span class="num gg-glow">{{
            pendCount === null ? "—" : pendCount.toLocaleString("pt-BR")
          }}</span>
        </span>
        <span class="kv" v-if="resumo?.corrected != null">
          <span class="lbl">corrigidas</span>
          <span class="num">{{
            resumo.corrected.toLocaleString("pt-BR")
          }}</span>
        </span>
        <span class="kv" v-if="resumo?.verified != null">
          <span class="lbl">verificadas</span>
          <span class="num">{{ resumo.verified.toLocaleString("pt-BR") }}</span>
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
        <button
          class="dt-btn"
          :class="{ 'dt-btn--accent': status === 'pending' }"
          @click="status = 'pending'"
        >
          pendentes
        </button>
        <button
          class="dt-btn"
          :class="{ 'dt-btn--accent': status === 'corrected' }"
          @click="status = 'corrected'"
        >
          corrigidas
        </button>
        <button
          class="dt-btn"
          :class="{ 'dt-btn--accent': status === 'verified' }"
          @click="status = 'verified'"
        >
          verificadas
        </button>
        <button
          class="dt-btn"
          :class="{ 'dt-btn--accent': status === '' }"
          @click="status = ''"
        >
          todas
        </button>
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
            <th>cpf</th>
            <th>nome</th>
            <th>campo</th>
            <th>esperado</th>
            <th>encontrado</th>
            <th>status</th>
            <th>quando</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="it in filtered" :key="it.id">
            <td class="mono">{{ fmtVal(it.cpf) }}</td>
            <td>{{ fmtVal(it.nome) }}</td>
            <td class="mono">{{ fmtVal(it.campo) }}</td>
            <td>{{ fmtVal(it.valor_esperado) }}</td>
            <td>{{ fmtVal(it.valor_encontrado) }}</td>
            <td>
              <span :class="statusTag(it.status)">{{ it.status ?? "—" }}</span>
            </td>
            <td class="mono">{{ fmtDate(it) }}</td>
            <td style="white-space: nowrap">
              <button
                v-if="it.status === 'pending'"
                class="dt-btn dt-btn--accent"
                style="padding: 5px 10px"
                @click="corrigir(it.id)"
              >
                corrigir
              </button>
              <button
                v-if="it.status === 'corrected'"
                class="dt-btn"
                style="padding: 5px 10px"
                @click="verificar(it.id)"
              >
                verificar
              </button>
            </td>
          </tr>
        </tbody>
      </table>

      <div v-else-if="loading" class="dt-empty">
        <span class="dot">●</span> carregando…
      </div>
      <div v-else class="dt-empty">
        sem divergências para "{{ status || "todas" }}"
      </div>
    </div>
  </main>
</template>
