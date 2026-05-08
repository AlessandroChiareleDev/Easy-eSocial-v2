<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { pyApi } from "@/services/pythonApi";
import { s1210AnualOverview } from "@/services/exploradorApi";

type Estado =
  | "sem_dados"
  | "processando"
  | "pronto_para_processar"
  | "concluido_com_erros"
  | "concluido"
  | "aguardando_mapeamento";

interface Celula {
  per_apur: string;
  lote_num: number;
  total: number;
  ok: number;
  erro: number;
  enviando: number;
  pendente: number;
  na: number;
  recibo_retificado?: number;
  aceito_com_aviso?: number;
  tem_xlsx: boolean;
  estado: Estado;
}

interface MesLinha {
  per_apur: string;
  lotes: Celula[];
}

interface OverviewAnual {
  ano: number;
  empresa_id?: number;
  meses: MesLinha[];
}

interface Empresa {
  id: number;
  nome: string;
  cnpj: string | null;
  ativo: boolean;
}

import { useEmpresaStore } from "@/stores/empresa";

const router = useRouter();
const empresaStore = useEmpresaStore();
const ano = ref<number>(2025);
const empresaId = computed<number>(() => empresaStore.currentId ?? 1);
const empresas = ref<Empresa[]>([]);
const overview = ref<OverviewAnual | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);

const ANOS = [2024, 2025, 2026];

const MES_LABEL: Record<string, string> = {
  "01": "Jan",
  "02": "Fev",
  "03": "Mar",
  "04": "Abr",
  "05": "Mai",
  "06": "Jun",
  "07": "Jul",
  "08": "Ago",
  "09": "Set",
  "10": "Out",
  "11": "Nov",
  "12": "Dez",
};

function labelMes(per: string): { label: string; iso: string } {
  const [y, m] = per.split("-");
  return { label: `${MES_LABEL[m ?? ""] ?? m} / ${y}`, iso: per };
}

const resumo = computed(() => {
  const out = {
    total: 0,
    ok: 0,
    erro: 0,
    pendente: 0,
    processando: 0,
    na: 0,
    mesesAtivos: 0,
    mesesTotal: 12,
    recibo_retificado: 0,
    aceito_com_aviso: 0,
  };
  if (!overview.value) return out;
  out.mesesTotal = overview.value.meses.length || 12;
  for (const mes of overview.value.meses) {
    let mesTemDados = false;
    for (const c of mes.lotes) {
      out.total += c.total;
      out.ok += c.ok;
      out.erro += c.erro;
      out.pendente += c.pendente;
      out.processando += c.enviando;
      out.na += c.na ?? 0;
      out.recibo_retificado += c.recibo_retificado ?? 0;
      out.aceito_com_aviso += c.aceito_com_aviso ?? 0;
      if (
        c.total > 0 ||
        c.ok > 0 ||
        c.erro > 0 ||
        c.pendente > 0 ||
        c.enviando > 0 ||
        (c.na ?? 0) > 0
      ) {
        mesTemDados = true;
      }
    }
    if (mesTemDados) out.mesesAtivos += 1;
  }
  return out;
});

function mesProgress(mes: MesLinha): number {
  let total = 0;
  let ok = 0;
  for (const c of mes.lotes) {
    total += c.total;
    ok += c.ok;
  }
  if (total <= 0) return 0;
  return Math.min(100, (ok / total) * 100);
}

function classeStatus(estado: Estado): string {
  switch (estado) {
    case "concluido":
      return "st st-ok";
    case "concluido_com_erros":
      return "st st-err";
    case "processando":
      return "st st-run";
    case "pronto_para_processar":
      return "st st-pend";
    case "aguardando_mapeamento":
      return "st st-map";
    default:
      return "st st-empty";
  }
}

function labelStatus(estado: Estado): string {
  switch (estado) {
    case "concluido":
      return "Concluído";
    case "concluido_com_erros":
      return "Concluído c/ erro";
    case "processando":
      return "Processando";
    case "pronto_para_processar":
      return "Pronto";
    case "aguardando_mapeamento":
      return "Aguardando mapeamento CPF";
    default:
      return "Sem dados";
  }
}

function fmt(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString("pt-BR");
}

function abrirCelula(c: Celula) {
  if (c.estado === "sem_dados") return;
  router.push({
    name: "s1210-mes",
    params: { per_apur: c.per_apur, lote_num: String(c.lote_num) },
  });
}

// APPA (id=1) usa 4 lotes fixos; demais (Solucoes em diante) usam lotes dinamicos.
const APPA_ID = 1;
const empresaUsaLotesDinamicos = computed(() => empresaId.value !== APPA_ID);

const maxLotes = computed(() => {
  if (!empresaUsaLotesDinamicos.value) return 4;
  if (!overview.value) return 1;
  let m = 1;
  for (const mes of overview.value.meses) {
    if (mes.lotes.length > m) m = mes.lotes.length;
  }
  return m;
});

const headersLotes = computed<number[]>(() => {
  const out: number[] = [];
  for (let i = 1; i <= maxLotes.value; i++) out.push(i);
  return out;
});

const gridStyle = computed(() => {
  // 140px (mes) + N colunas de lote + (acoes 90px se dinamico)
  const cols = `140px repeat(${maxLotes.value}, 1fr)${
    empresaUsaLotesDinamicos.value ? " 90px" : ""
  }`;
  return { gridTemplateColumns: cols };
});

function celulaDoLote(mes: MesLinha, lote_num: number): Celula | null {
  return mes.lotes.find((c) => c.lote_num === lote_num) ?? null;
}

async function dividirLote(mes: MesLinha) {
  if (!empresaUsaLotesDinamicos.value) return;
  if (mes.lotes.length >= 2) return;
  const ok = window.confirm(
    `Dividir o lote 1 de ${labelMes(mes.per_apur).label} em 2 lotes iguais?`,
  );
  if (!ok) return;
  try {
    await fetch(
      `/py-api/api/s1210-repo/anual/dividir-lote?empresa_id=${empresaId.value}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          per_apur: mes.per_apur,
          lote_origem: 1,
          lote_destino: 2,
        }),
      },
    );
    await carregar();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Falha ao dividir lote";
  }
}

async function unirLotes(mes: MesLinha) {
  if (!empresaUsaLotesDinamicos.value) return;
  if (mes.lotes.length < 2) return;
  const ok = window.confirm(
    `Unir os ${mes.lotes.length} lotes de ${labelMes(mes.per_apur).label} em um único lote?`,
  );
  if (!ok) return;
  try {
    // Move lote N..2 -> 1 (do maior pro menor)
    for (let n = mes.lotes.length; n >= 2; n--) {
      await fetch(
        `/py-api/api/s1210-repo/anual/unir-lotes?empresa_id=${empresaId.value}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            per_apur: mes.per_apur,
            lote_origem: n,
            lote_destino: 1,
          }),
        },
      );
    }
    await carregar();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Falha ao unir lotes";
  }
}

function processarLotes() {
  // Endpoint ainda pendente de confirmação no backend Python.
  // eslint-disable-next-line no-console
  console.log(
    "[S-1210] Processar lotes — ano:",
    ano.value,
    "empresa:",
    empresaId.value,
  );
}

function voltarRepositorio() {
  router.push("/");
}

async function carregar() {
  loading.value = true;
  error.value = null;
  try {
    overview.value = await s1210AnualOverview(ano.value, empresaId.value);
  } catch (e) {
    const msg = e instanceof Error ? e.message : "Falha ao carregar S-1210";
    error.value = msg;
    overview.value = null;
  } finally {
    loading.value = false;
  }
}

watch([ano, empresaId], carregar);
onMounted(() => {
  void carregar();
});
</script>

<template>
  <div class="s1210-page">
    <!-- LOCAL TOPBAR (filtros + ações da tela) -->
    <header class="local-topbar">
      <div class="crumb-block">
        <div class="crumb">REPOSITÓRIO · S-1210 · ANUAL</div>
        <div class="title">
          S-1210 Anual
          <span
            class="repo-pill"
            :title="error ? 'falha ao consultar repo' : 'overview sincronizado'"
            :class="{ 'repo-pill--err': !!error }"
          >
            {{ error ? "repo offline" : "repo sincronizado" }}
          </span>
        </div>
      </div>

      <!-- Year switcher (pílulas) -->
      <div class="year-switcher" role="tablist" aria-label="Ano">
        <button
          v-for="a in ANOS"
          :key="a"
          class="year-btn"
          :class="{ active: ano === a }"
          role="tab"
          :aria-selected="ano === a"
          @click="ano = a"
        >
          {{ a }}
        </button>
      </div>

      <div class="local-actions">
        <button
          class="icon-btn"
          :disabled="loading"
          title="Atualizar"
          @click="carregar"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <polyline points="23 4 23 10 17 10" />
            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
          </svg>
        </button>
        <button class="btn-power" :disabled="loading" @click="processarLotes">
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.5"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <polygon points="5 3 19 12 5 21 5 3" />
          </svg>
          Processar lotes
        </button>
      </div>
    </header>

    <!-- PAGE HEADER -->
    <section class="page-header">
      <div>
        <h1>
          Visão Anual <span class="accent">{{ ano }}</span>
        </h1>
        <p>
          <button class="link-back" @click="voltarRepositorio">
            ← REPOSITÓRIO S-1210
          </button>
          · 12 meses · 4 lotes por mês
        </p>
      </div>
    </section>

    <!-- ERROR / LOADING -->
    <div v-if="error" class="state-err" role="alert">
      <strong>FastAPI offline ou rota indisponível:</strong>
      {{ error }}
      <div class="hint-cmd">
        <code
          >cd Easy-Social/python-scripts; uvicorn bot_api:app --port 8000
          --reload</code
        >
      </div>
    </div>
    <div v-else-if="loading" class="state-loading">
      <span class="dot"></span> carregando visão anual…
    </div>

    <!-- KPIS -->
    <div v-if="!error" class="kpi-row" :class="{ 'kpi-row--loading': loading }">
      <div class="kpi-card brand">
        <div class="kpi-label">Meses ativos</div>
        <div class="kpi-value">
          {{ resumo.mesesAtivos }} <span class="kpi-divider">/</span> 12
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Total escopo</div>
        <div class="kpi-value">{{ fmt(resumo.total) }}</div>
      </div>
      <div class="kpi-card ok">
        <div class="kpi-label">OK <span class="na-inline">(N/A)</span></div>
        <div class="kpi-value">
          {{ fmt(resumo.ok) }}
          <span class="na-inline">({{ fmt(resumo.na) }})</span>
        </div>
      </div>
      <div class="kpi-card err">
        <div class="kpi-label">Erro</div>
        <div class="kpi-value">{{ fmt(resumo.erro) }}</div>
      </div>
      <div class="kpi-card pend">
        <div class="kpi-label">Pendente</div>
        <div class="kpi-value">{{ fmt(resumo.pendente) }}</div>
      </div>
      <div class="kpi-card run">
        <div class="kpi-label">Processando</div>
        <div class="kpi-value">{{ fmt(resumo.processando) }}</div>
      </div>
      <div
        v-if="resumo.recibo_retificado > 0"
        class="kpi-card kpi-flag kpi-flag--retif"
        title="CPFs cuja resposta do eSocial foi 401-459: o recibo do S-1200 referenciado foi retificado externamente. Necessario reextrair recibos atualizados (ZIP novo) antes de retentar."
      >
        <div class="kpi-label">🔁 Recibo retificado</div>
        <div class="kpi-value retif">{{ fmt(resumo.recibo_retificado) }}</div>
      </div>
      <div
        v-if="resumo.aceito_com_aviso > 0"
        class="kpi-card kpi-flag kpi-flag--aviso"
        title="CPFs com codigo 202: aceito pelo eSocial com advertencia (geralmente rubrica 1863 deducao dependente). Nao precisa reenviar."
      >
        <div class="kpi-label">⚠ Aceito c/ aviso</div>
        <div class="kpi-value aviso">{{ fmt(resumo.aceito_com_aviso) }}</div>
      </div>
    </div>

    <!-- TIMELINE 12x4 -->
    <section v-if="overview && !error" class="timeline">
      <header class="timeline-head">
        <div>
          <h3>Timeline 12 × 4</h3>
          <p>cada célula representa um lote · clique para abrir</p>
        </div>
        <div class="legend">
          <div class="legend-item">
            <span class="legend-dot ok"></span>Concluído
          </div>
          <div class="legend-item">
            <span class="legend-dot err"></span>C/ erro
          </div>
          <div class="legend-item">
            <span class="legend-dot pend"></span>Pronto
          </div>
          <div class="legend-item">
            <span class="legend-dot run"></span>Processando
          </div>
          <div class="legend-item">
            <span class="legend-dot map"></span>Map. CPF
          </div>
          <div class="legend-item">
            <span class="legend-dot empty"></span>Sem dados
          </div>
        </div>
      </header>

      <div class="grid-table" :style="gridStyle">
        <div class="grid-th grid-th-mes">Mês</div>
        <div v-for="n in headersLotes" :key="`th-${n}`" class="grid-th">
          Lote {{ n }}
        </div>
        <div v-if="empresaUsaLotesDinamicos" class="grid-th">Ações</div>

        <div v-for="mes in overview.meses" :key="mes.per_apur" class="grid-row">
          <div class="cell-mes">
            <div class="cell-mes-label">{{ labelMes(mes.per_apur).label }}</div>
            <div class="cell-mes-sub">{{ mes.per_apur }}</div>
            <div
              class="cell-mes-bar"
              :title="`${mesProgress(mes).toFixed(1)}% ok`"
            >
              <div
                class="cell-mes-bar-fill"
                :style="{ width: mesProgress(mes) + '%' }"
              ></div>
            </div>
          </div>

          <template v-for="n in headersLotes" :key="`${mes.per_apur}-${n}`">
            <button
              v-if="celulaDoLote(mes, n)"
              class="cell"
              :class="{
                'cell-empty': celulaDoLote(mes, n)!.estado === 'sem_dados',
              }"
              :disabled="celulaDoLote(mes, n)!.estado === 'sem_dados'"
              :title="labelStatus(celulaDoLote(mes, n)!.estado)"
              @click="abrirCelula(celulaDoLote(mes, n)!)"
            >
              <span :class="classeStatus(celulaDoLote(mes, n)!.estado)">
                {{ labelStatus(celulaDoLote(mes, n)!.estado) }}
              </span>
              <div
                v-if="celulaDoLote(mes, n)!.estado !== 'sem_dados'"
                class="nums"
              >
                <span
                  ><b>{{ fmt(celulaDoLote(mes, n)!.total) }}</b> escopo</span
                >
                <span class="ok"
                  ><b>{{ fmt(celulaDoLote(mes, n)!.ok) }}</b> ok</span
                >
                <span v-if="celulaDoLote(mes, n)!.erro > 0" class="err"
                  ><b>{{ fmt(celulaDoLote(mes, n)!.erro) }}</b> erro</span
                >
                <span
                  v-if="
                    celulaDoLote(mes, n)!.pendente +
                      celulaDoLote(mes, n)!.enviando >
                    0
                  "
                  class="pend"
                  ><b>{{
                    fmt(
                      celulaDoLote(mes, n)!.pendente +
                        celulaDoLote(mes, n)!.enviando,
                    )
                  }}</b>
                  pend</span
                >
                <span v-if="(celulaDoLote(mes, n)!.na ?? 0) > 0" class="na"
                  ><b>{{ fmt(celulaDoLote(mes, n)!.na) }}</b> N/A</span
                >
              </div>
              <div
                v-if="
                  (celulaDoLote(mes, n)!.recibo_retificado ?? 0) > 0 ||
                  (celulaDoLote(mes, n)!.aceito_com_aviso ?? 0) > 0
                "
                class="cell-flags"
              >
                <span
                  v-if="(celulaDoLote(mes, n)!.recibo_retificado ?? 0) > 0"
                  class="cell-flag cell-flag--retif"
                  :title="`${celulaDoLote(mes, n)!.recibo_retificado} CPF(s) com recibo retificado externamente (eSocial 401-459). Reextrair via ZIP novo.`"
                  >🔁 {{ celulaDoLote(mes, n)!.recibo_retificado }} retif</span
                >
                <span
                  v-if="(celulaDoLote(mes, n)!.aceito_com_aviso ?? 0) > 0"
                  class="cell-flag cell-flag--aviso"
                  :title="`${celulaDoLote(mes, n)!.aceito_com_aviso} CPF(s) aceitos com advertencia (codigo 202).`"
                  >⚠ {{ celulaDoLote(mes, n)!.aceito_com_aviso }} aviso</span
                >
              </div>
              <div
                v-if="celulaDoLote(mes, n)!.estado === 'aguardando_mapeamento'"
                class="hint"
              >
                Clique para ver lista com identificador temporário
              </div>
            </button>
            <div v-else class="cell cell-vazio" />
          </template>

          <div v-if="empresaUsaLotesDinamicos" class="cell cell-acao">
            <button
              v-if="mes.lotes.length === 1 && (mes.lotes[0]?.total ?? 0) > 0"
              class="btn-mini"
              title="Dividir o lote 1 em 2 lotes iguais"
              @click="dividirLote(mes)"
            >
              + Lote
            </button>
            <button
              v-else-if="mes.lotes.length >= 2"
              class="btn-mini btn-mini-warn"
              title="Unir todos os lotes em um único"
              @click="unirLotes(mes)"
            >
              ↩ Unir
            </button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.s1210-page {
  max-width: 1480px;
  margin: 0 auto;
  padding: 8px 28px 64px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* ========== LOCAL TOPBAR ========== */
.local-topbar {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 14px 20px;
  background: var(--glass-bg, rgba(15, 23, 42, 0.55));
  backdrop-filter: blur(28px) saturate(140%);
  -webkit-backdrop-filter: blur(28px) saturate(140%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 18px;
  position: relative;
  box-shadow:
    0 8px 32px 0 rgba(0, 0, 0, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
}
.local-topbar::after {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.18),
    transparent
  );
}
.crumb-block {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.crumb {
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 13px;
  color: var(--text-muted);
  letter-spacing: 0.05em;
}
.title {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.02em;
  display: flex;
  align-items: center;
  gap: 10px;
}

.repo-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px 4px 8px;
  background: rgba(61, 242, 75, 0.06);
  border: 1px solid rgba(61, 242, 75, 0.28);
  border-radius: 100px;
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--secondary);
  box-shadow:
    0 0 10px rgba(61, 242, 75, 0.18),
    inset 0 0 8px rgba(61, 242, 75, 0.06);
  text-shadow: 0 0 6px rgba(61, 242, 75, 0.5);
}
.repo-pill::before {
  content: "";
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--secondary);
  box-shadow:
    0 0 8px var(--secondary),
    0 0 14px rgba(61, 242, 75, 0.7);
  animation: live-pulse 1.6s ease-in-out infinite;
}
.repo-pill--err {
  background: rgba(225, 29, 72, 0.06);
  border-color: rgba(225, 29, 72, 0.4);
  color: #ff8a9c;
  text-shadow: 0 0 6px rgba(255, 90, 110, 0.4);
  box-shadow: 0 0 10px rgba(225, 29, 72, 0.18);
}
.repo-pill--err::before {
  background: #ff6a7d;
  box-shadow:
    0 0 8px #ff6a7d,
    0 0 14px rgba(255, 90, 110, 0.7);
}
@keyframes live-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.55;
  }
}

/* Year switcher (pílulas) */
.year-switcher {
  margin-left: 18px;
  display: flex;
  gap: 4px;
  padding: 3px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 100px;
}
.year-btn {
  padding: 6px 14px;
  font-size: 14px;
  font-weight: 500;
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  border-radius: 100px;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all 0.28s cubic-bezier(0.32, 0.72, 0, 1);
}
.year-btn.active {
  background: var(--primary);
  color: var(--text-on-primary, #1a0f15);
  box-shadow: 0 4px 16px rgba(240, 209, 229, 0.25);
}
.year-btn:not(.active):hover {
  color: var(--text-primary, #fff);
  background: rgba(255, 255, 255, 0.04);
}

.local-actions {
  margin-left: auto;
  display: flex;
  gap: 8px;
  align-items: center;
}
.empresa-select {
  height: 36px;
  padding: 0 12px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  color: var(--text-primary, #fff);
  font: inherit;
  font-size: 14px;
  letter-spacing: 0.02em;
  cursor: pointer;
  max-width: 280px;
  transition: all 0.28s cubic-bezier(0.32, 0.72, 0, 1);
}
.empresa-select:hover:not(:disabled) {
  background: rgba(240, 209, 229, 0.08);
  border-color: rgba(240, 209, 229, 0.25);
}
.empresa-select:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.icon-btn {
  width: 36px;
  height: 36px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  display: grid;
  place-items: center;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.28s cubic-bezier(0.32, 0.72, 0, 1);
}
.icon-btn:hover:not(:disabled) {
  background: rgba(240, 209, 229, 0.1);
  color: var(--text-primary, #fff);
  border-color: rgba(240, 209, 229, 0.25);
}
.icon-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.icon-btn svg {
  width: 16px;
  height: 16px;
  stroke-width: 1.75;
}

/* btn-power — Ghost Green halo */
.btn-power {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 9px 16px;
  background: radial-gradient(
    ellipse at 50% 120%,
    rgba(61, 242, 75, 0.35) 0%,
    rgba(61, 242, 75, 0.08) 35%,
    rgba(15, 23, 42, 0.85) 70%
  );
  color: #d4ffd9;
  font-weight: 600;
  font-size: 14px;
  letter-spacing: -0.01em;
  border-radius: 14px;
  border: 1px solid rgba(61, 242, 75, 0.55);
  cursor: pointer;
  transition: all 0.28s cubic-bezier(0.32, 0.72, 0, 1);
  box-shadow:
    inset 0 1px 0 rgba(61, 242, 75, 0.35),
    inset 0 -8px 16px rgba(61, 242, 75, 0.18),
    0 0 0 1px rgba(61, 242, 75, 0.18),
    0 0 18px rgba(61, 242, 75, 0.45),
    0 0 48px rgba(61, 242, 75, 0.22);
  text-shadow: 0 0 8px rgba(61, 242, 75, 0.6);
}
.btn-power:hover:not(:disabled) {
  transform: translateY(-1px);
  color: #fff;
  border-color: var(--secondary);
  box-shadow:
    inset 0 1px 0 rgba(61, 242, 75, 0.5),
    inset 0 -8px 20px rgba(61, 242, 75, 0.28),
    0 0 0 1px rgba(61, 242, 75, 0.4),
    0 0 28px rgba(61, 242, 75, 0.7),
    0 0 80px rgba(61, 242, 75, 0.35);
}
.btn-power:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

/* ========== PAGE HEADER ========== */
.page-header {
  display: flex;
  align-items: end;
  justify-content: space-between;
}
.page-header h1 {
  font-size: 26px;
  font-weight: 600;
  letter-spacing: -0.03em;
  margin: 0;
}
.page-header h1 .accent {
  color: var(--primary);
  text-shadow: 0 0 6px rgba(255, 255, 255, 0.08);
}
.page-header p {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 4px 0 0;
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  display: flex;
  align-items: center;
  gap: 6px;
}
.link-back {
  background: transparent;
  border: none;
  padding: 0;
  font: inherit;
  color: var(--text-secondary);
  cursor: pointer;
  letter-spacing: 0.04em;
  transition: color 0.18s;
}
.link-back:hover {
  color: var(--primary);
}

/* ========== STATES ========== */
.state-err,
.state-loading {
  padding: 18px 22px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(28px) saturate(140%);
  -webkit-backdrop-filter: blur(28px) saturate(140%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 14px;
  color: var(--text-secondary);
}
.state-err {
  border-color: rgba(225, 29, 72, 0.35);
  color: #ffd1d8;
}
.state-err strong {
  color: #ff8a9c;
  display: block;
  margin-bottom: 4px;
}
.hint-cmd {
  margin-top: 8px;
}
.hint-cmd code {
  background: rgba(255, 255, 255, 0.04);
  padding: 4px 8px;
  border-radius: 6px;
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 13px;
  color: var(--text-secondary);
  display: inline-block;
}
.state-loading .dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--secondary);
  margin-right: 8px;
  box-shadow: 0 0 8px var(--secondary);
  animation: live-pulse 1.4s ease-in-out infinite;
}

/* ========== KPI ROW ========== */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  transition: opacity 0.2s;
}
.kpi-row--loading {
  opacity: 0.5;
}
@media (max-width: 1100px) {
  .kpi-row {
    grid-template-columns: repeat(3, 1fr);
  }
}
@media (max-width: 600px) {
  .kpi-row {
    grid-template-columns: repeat(2, 1fr);
  }
}
.kpi-card {
  padding: 16px;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(28px) saturate(140%);
  -webkit-backdrop-filter: blur(28px) saturate(140%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 18px;
  box-shadow:
    0 8px 32px 0 rgba(0, 0, 0, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
  position: relative;
  overflow: hidden;
  transition: all 0.28s cubic-bezier(0.32, 0.72, 0, 1);
}
.kpi-card::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.18),
    transparent
  );
}
.kpi-card:hover {
  transform: translateY(-2px);
  border-color: rgba(255, 255, 255, 0.16);
}
.kpi-label {
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 13px;
  color: var(--text-muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 8px;
}
.kpi-value {
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.03em;
  line-height: 1;
  font-feature-settings: "tnum";
  color: var(--text-primary, #fff);
}
.kpi-divider {
  color: var(--text-muted);
  font-weight: 400;
  margin: 0 2px;
}
.na-inline {
  display: inline-flex;
  align-items: center;
  font-size: 13px;
  font-weight: 600;
  color: #7cb1ff;
  background: rgba(56, 109, 199, 0.18);
  border: 1px solid rgba(124, 177, 255, 0.35);
  font-family: "JetBrains Mono", ui-monospace, monospace;
  margin-left: 6px;
  padding: 2px 8px;
  border-radius: 6px;
  letter-spacing: 0.02em;
  text-shadow: 0 0 8px rgba(124, 177, 255, 0.45);
}
.kpi-card.brand .kpi-value {
  color: var(--primary);
  text-shadow: 0 0 6px rgba(255, 255, 255, 0.08);
}
.kpi-card.ok .kpi-value {
  color: var(--secondary);
  text-shadow: 0 0 6px rgba(255, 255, 255, 0.08);
}
.kpi-card.err .kpi-value {
  color: #ff6a7d;
  text-shadow: 0 0 6px rgba(255, 255, 255, 0.08);
}
.kpi-card.pend .kpi-value {
  color: #f59e0b;
  text-shadow: 0 0 6px rgba(255, 255, 255, 0.08);
}
.kpi-card.run .kpi-value {
  color: #60a5fa;
  text-shadow: 0 0 6px rgba(255, 255, 255, 0.08);
}

/* ========== TIMELINE ========== */
.timeline {
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(28px) saturate(140%);
  -webkit-backdrop-filter: blur(28px) saturate(140%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 24px;
  box-shadow:
    0 8px 32px 0 rgba(0, 0, 0, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
  overflow: hidden;
  position: relative;
}
.timeline::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.18),
    transparent
  );
}

.timeline-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 22px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-wrap: wrap;
  gap: 14px;
}
.timeline-head h3 {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.01em;
  margin: 0;
  color: var(--text-primary, #fff);
}
.timeline-head p {
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 13px;
  color: var(--text-muted);
  margin: 2px 0 0;
}

.legend {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 13px;
  color: var(--text-secondary);
}
.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
}
.legend-dot.ok {
  background: var(--secondary);
  box-shadow:
    0 0 6px rgba(61, 242, 75, 0.5),
    0 0 12px rgba(61, 242, 75, 0.5);
  animation: live-pulse 2s ease-in-out infinite;
}
.legend-dot.err {
  background: #ff6a7d;
  box-shadow: 0 0 6px rgba(255, 90, 110, 0.5);
}
.legend-dot.pend {
  background: #f59e0b;
}
.legend-dot.run {
  background: #60a5fa;
}
.legend-dot.map {
  background: var(--primary);
}
.legend-dot.empty {
  background: rgba(255, 255, 255, 0.08);
}

/* ========== GRID 12 x N (lotes dinamicos por empresa) ========== */
.grid-table {
  display: grid;
  /* grid-template-columns vem inline via :style="gridStyle" */
  gap: 0;
}
.cell-vazio {
  background: rgba(255, 255, 255, 0.015);
}
.cell-acao {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
}
.btn-mini {
  background: rgba(108, 240, 160, 0.12);
  border: 1px solid rgba(108, 240, 160, 0.3);
  color: #6cf0a0;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  letter-spacing: 0.04em;
}
.btn-mini:hover {
  background: rgba(108, 240, 160, 0.22);
}
.btn-mini-warn {
  background: rgba(255, 200, 80, 0.12);
  border-color: rgba(255, 200, 80, 0.3);
  color: #ffd060;
}
.btn-mini-warn:hover {
  background: rgba(255, 200, 80, 0.22);
}
.grid-th {
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.02);
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 13px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  text-align: left;
}
.grid-th-mes {
  padding-left: 22px;
}
.grid-row {
  display: contents;
}
.grid-row > * {
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}
.grid-row:last-child > * {
  border-bottom: none;
}

.cell-mes {
  padding: 14px 22px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: rgba(255, 255, 255, 0.015);
  border-right: 1px solid rgba(255, 255, 255, 0.04);
}
.cell-mes-label {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--text-primary, #fff);
}
.cell-mes-sub {
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 13px;
  color: var(--text-muted);
}
.cell-mes-bar {
  margin-top: 6px;
  height: 3px;
  width: 100%;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 2px;
  overflow: hidden;
}
.cell-mes-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--secondary), var(--primary));
  border-radius: 2px;
  box-shadow: 0 0 6px rgba(61, 242, 75, 0.4);
  transition: width 0.4s cubic-bezier(0.32, 0.72, 0, 1);
}

.cell {
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  text-align: left;
  cursor: pointer;
  transition: all 0.28s cubic-bezier(0.32, 0.72, 0, 1);
  border-right: 1px solid rgba(255, 255, 255, 0.04);
  position: relative;
  min-height: 84px;
  background: transparent;
  border-top: none;
  border-left: none;
  font: inherit;
  color: inherit;
}
.grid-row > .cell:last-child {
  border-right: none;
}
.cell:hover:not(.cell-empty):not(:disabled) {
  background: rgba(240, 209, 229, 0.04);
}
.cell:hover:not(.cell-empty):not(:disabled)::after {
  content: "→";
  position: absolute;
  top: 12px;
  right: 14px;
  color: var(--primary);
  font-weight: 600;
  text-shadow: 0 0 6px rgba(240, 209, 229, 0.5);
}

.cell-empty {
  cursor: not-allowed;
  background: repeating-linear-gradient(
    45deg,
    transparent,
    transparent 8px,
    rgba(255, 255, 255, 0.015) 8px,
    rgba(255, 255, 255, 0.015) 16px
  );
}
.cell:disabled {
  cursor: not-allowed;
}

/* Status pill */
.st {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  border-radius: 6px;
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 13px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  width: fit-content;
}
.st::before {
  content: "";
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}
.st-ok {
  background: rgba(61, 242, 75, 0.1);
  color: var(--secondary);
  text-shadow: 0 0 6px rgba(61, 242, 75, 0.4);
}
.st-err {
  background: rgba(225, 29, 72, 0.12);
  color: #ff6a7d;
}
.st-pend {
  background: rgba(245, 158, 11, 0.12);
  color: #f59e0b;
}
.st-run {
  background: rgba(96, 165, 250, 0.12);
  color: #60a5fa;
}
.st-map {
  background: rgba(240, 209, 229, 0.1);
  color: var(--primary);
}
.st-empty {
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-muted);
}

/* Numbers */
.nums {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 13px;
  color: var(--text-secondary);
  font-feature-settings: "tnum";
}
.nums .ok {
  color: var(--secondary);
}
.nums .err {
  color: #ff6a7d;
}
.nums .pend {
  color: #f59e0b;
}
.nums .na {
  color: #7cb1ff;
  opacity: 1;
}
.nums b {
  font-weight: 600;
  color: var(--text-primary, #fff);
}
.nums .ok b {
  color: var(--secondary);
}
.nums .err b {
  color: #ff8a9c;
}
.nums .pend b {
  color: #fbbf24;
}
.nums .na b {
  color: #a8caff;
  text-shadow: 0 0 6px rgba(124, 177, 255, 0.45);
}

.hint {
  font-size: 13px;
  color: var(--primary);
  font-style: italic;
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  text-shadow: 0 0 6px rgba(240, 209, 229, 0.3);
}

/* Flags semanticas (recibo retificado / aceito c/ aviso) */
.cell-flags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}
.cell-flag {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.03em;
  cursor: help;
}
.cell-flag--retif {
  background: rgba(255, 130, 80, 0.18);
  color: #ffaa70;
  border: 1px solid rgba(255, 130, 80, 0.4);
  box-shadow: 0 0 8px rgba(255, 130, 80, 0.25);
}
.cell-flag--aviso {
  background: rgba(255, 200, 80, 0.18);
  color: #ffd060;
  border: 1px solid rgba(255, 200, 80, 0.35);
}
.kpi-card.kpi-flag {
  cursor: help;
}
.kpi-flag--retif {
  border-color: rgba(255, 130, 80, 0.4) !important;
  background: rgba(255, 130, 80, 0.06) !important;
}
.kpi-flag--aviso {
  border-color: rgba(255, 200, 80, 0.35) !important;
  background: rgba(255, 200, 80, 0.06) !important;
}
.kpi-value.retif {
  color: #ffaa70;
}
.kpi-value.aviso {
  color: #ffd060;
}
</style>
