<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { RouterLink } from "vue-router";
import { api } from "@/services/api";

interface Atividade {
  id?: number | string;
  operador?: string;
  username?: string;
  acao?: string;
  action?: string;
  detalhes?: string;
  details?: string;
  ip?: string;
  user_agent?: string;
  criado_em?: string;
  created_at?: string;
  empresa_id?: number | string;
}

interface AtividadesResponse {
  total?: number;
  atividades?: Atividade[];
  items?: Atividade[];
  data?: Atividade[];
  rows?: Atividade[];
}

const items = ref<Atividade[]>([]);
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
    const res = await api.get<AtividadesResponse | Atividade[]>(
      `/admin/atividades?limit=${limit.value}&offset=${offset}`,
    );
    if (Array.isArray(res)) {
      items.value = res;
      total.value = res.length;
    } else {
      items.value = res.atividades ?? res.items ?? res.data ?? res.rows ?? [];
      total.value = res.total ?? items.value.length;
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : "Falha ao carregar logs";
    error.value = msg;
    items.value = [];
  } finally {
    loading.value = false;
  }
}

function pickDate(it: Atividade): string {
  const raw = it.criado_em || it.created_at;
  if (!raw) return "—";
  try {
    return new Date(raw).toLocaleString("pt-BR");
  } catch {
    return raw;
  }
}
function pickAcao(it: Atividade): string {
  return it.acao || it.action || "—";
}
function pickOperador(it: Atividade): string {
  return it.operador || it.username || "—";
}
function pickDetalhes(it: Atividade): string {
  return it.detalhes || it.details || "";
}

watch([page, limit], load);
onMounted(load);
</script>

<template>
  <main class="page">
    <RouterLink to="/" class="back">← Painel</RouterLink>

    <header class="head">
      <div>
        <h1>Logs de Sistema</h1>
        <p class="sub">
          Auditoria · histórico de operações · respostas do eSocial.
        </p>
      </div>
      <div class="counts">
        <span class="kv">
          <span class="lbl">total</span>
          <span class="num gg-glow">{{
            total === null ? "—" : total.toLocaleString("pt-BR")
          }}</span>
        </span>
      </div>
    </header>

    <div class="toolbar liquid-glass">
      <input
        v-model="filterText"
        type="search"
        placeholder="filtrar nesta página…"
        class="search"
      />
      <div class="pager">
        <button class="pg-btn" :disabled="page <= 1 || loading" @click="page--">
          ← anterior
        </button>
        <span class="pg-info"
          >pág {{ page }} / {{ totalPages }} · {{ items.length }}</span
        >
        <button
          class="pg-btn"
          :disabled="page >= totalPages || loading"
          @click="page++"
        >
          próxima →
        </button>
        <button class="pg-btn refresh" :disabled="loading" @click="load">
          {{ loading ? "carregando…" : "↻ atualizar" }}
        </button>
      </div>
    </div>

    <div v-if="error" class="err liquid-glass" role="alert">
      <strong>backend indisponível:</strong> {{ error }}
    </div>

    <div class="table-wrap liquid-glass">
      <table v-if="filtered.length > 0">
        <thead>
          <tr>
            <th class="col-when">quando</th>
            <th class="col-op">operador</th>
            <th class="col-action">ação</th>
            <th class="col-det">detalhes</th>
            <th class="col-ip">ip</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(it, i) in filtered" :key="it.id ?? i">
            <td class="when">{{ pickDate(it) }}</td>
            <td class="op">{{ pickOperador(it) }}</td>
            <td class="action">
              <span class="tag">{{ pickAcao(it) }}</span>
            </td>
            <td class="det" :title="pickDetalhes(it)">
              {{ pickDetalhes(it) }}
            </td>
            <td class="ip">{{ it.ip ?? "—" }}</td>
          </tr>
        </tbody>
      </table>

      <div v-else-if="loading" class="empty">
        <span class="dot">●</span> carregando do backend…
      </div>
      <div v-else class="empty">
        sem registros nesta página
        <span v-if="filterText" class="muted"
          >· filtro: "{{ filterText }}"</span
        >
      </div>
    </div>
  </main>
</template>

<style scoped>
.page {
  max-width: 1280px;
  margin: 0 auto;
  padding: 16px 32px 64px;
}
.back {
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 12px;
  color: var(--text-muted);
  text-decoration: none;
  letter-spacing: 0.1em;
}
.back:hover {
  color: var(--primary);
}

.head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin: 16px 0 22px;
}
h1 {
  font-size: 28px;
  font-weight: 500;
  letter-spacing: -0.02em;
  margin: 0 0 4px;
}
.sub {
  color: var(--text-muted);
  font-size: 13px;
  margin: 0;
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  letter-spacing: 0.04em;
}
.counts .kv {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}
.counts .lbl {
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 9.5px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.18em;
}
.counts .num {
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.02em;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 14px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.search {
  flex: 1;
  min-width: 220px;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 9px 12px;
  color: var(--text-primary);
  font-size: 13px;
  font-family: inherit;
  outline: none;
  transition:
    border-color var(--duration-base) var(--ease-glass),
    box-shadow var(--duration-base) var(--ease-glass);
}
.search:focus {
  border-color: rgba(61, 242, 75, 0.4);
  box-shadow: 0 0 0 3px rgba(61, 242, 75, 0.1);
}

.pager {
  display: flex;
  align-items: center;
  gap: 8px;
}
.pg-btn {
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 7px 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-glass);
}
.pg-btn:not(:disabled):hover {
  border-color: rgba(61, 242, 75, 0.4);
  color: #fff;
  box-shadow: 0 0 14px rgba(61, 242, 75, 0.18);
}
.pg-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.pg-btn.refresh {
  border-color: rgba(61, 242, 75, 0.3);
  color: var(--secondary);
}
.pg-info {
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 11px;
  color: var(--text-muted);
  letter-spacing: 0.06em;
}

.err {
  padding: 14px 18px;
  margin-bottom: 14px;
  color: #ff8a9c;
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 12.5px;
  border-color: rgba(255, 90, 110, 0.32) !important;
}

.table-wrap {
  padding: 0;
  overflow-x: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
thead th {
  text-align: left;
  padding: 14px 16px 12px;
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  color: var(--text-muted);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  white-space: nowrap;
  background: rgba(11, 14, 20, 0.4);
}
tbody td {
  padding: 11px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  vertical-align: top;
}
tbody tr:hover {
  background: rgba(61, 242, 75, 0.03);
}
.when {
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 11.5px;
  color: var(--text-muted);
  white-space: nowrap;
}
.op {
  font-weight: 500;
  white-space: nowrap;
}
.tag {
  display: inline-block;
  padding: 3px 9px;
  background: rgba(61, 242, 75, 0.06);
  border: 1px solid rgba(61, 242, 75, 0.25);
  border-radius: 100px;
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 10.5px;
  color: var(--secondary);
  text-shadow: 0 0 6px rgba(61, 242, 75, 0.4);
  letter-spacing: 0.04em;
}
.det {
  color: var(--text-secondary);
  font-size: 12.5px;
  max-width: 480px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ip {
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 11.5px;
  color: var(--text-muted);
  white-space: nowrap;
}

.empty {
  padding: 60px 24px;
  text-align: center;
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 12px;
  color: var(--text-muted);
  letter-spacing: 0.06em;
}
.empty .dot {
  color: var(--secondary);
  text-shadow: 0 0 8px rgba(61, 242, 75, 0.6);
  margin-right: 6px;
}
.muted {
  margin-left: 8px;
  opacity: 0.7;
}
</style>
