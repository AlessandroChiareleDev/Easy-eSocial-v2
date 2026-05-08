<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import {
  estadoEnvio,
  listarMesesTimeline,
  reguaMes,
  type EstadoEnvioItem,
  type EstadoEnvioResp,
  type ReguaResp,
  type TimelineMesRow,
} from "@/services/exploradorApi";
import TimelineRegua from "./TimelineRegua.vue";
import DrawerCadeiaCpf from "./DrawerCadeiaCpf.vue";

const props = defineProps<{ empresaId: number }>();

const meses = ref<TimelineMesRow[]>([]);
const carregandoMeses = ref(false);
const erroMeses = ref<string | null>(null);

const perApurSel = ref<string | null>(null);
const regua = ref<ReguaResp | null>(null);
const carregandoRegua = ref(false);

const envioSelId = ref<number | null>(null);
const estado = ref<EstadoEnvioResp | null>(null);
const carregandoEstado = ref(false);

const cpfSel = ref<string | null>(null);
const filtroCpf = ref("");

const isHead = computed(() => {
  if (!regua.value || !envioSelId.value) return false;
  return regua.value.timeline_mes.head_envio_id === envioSelId.value;
});

const envioSelecionado = computed(() => {
  if (!regua.value || !envioSelId.value) return null;
  return regua.value.envios.find((e) => e.id === envioSelId.value) ?? null;
});

const explicacaoFalha = computed<string | null>(() => {
  const r = (envioSelecionado.value?.resumo ?? null) as Record<
    string,
    unknown
  > | null;
  if (!r) return null;
  const v = r["explicacao_falha"];
  return typeof v === "string" && v.trim() ? v : null;
});

const ambienteReal = computed<string | null>(() => {
  const r = (envioSelecionado.value?.resumo ?? null) as Record<
    string,
    unknown
  > | null;
  if (!r) return null;
  const v = r["ambiente_real"];
  return typeof v === "string" ? v : null;
});

const histogramaErros = computed<Array<[string, number]>>(() => {
  const r = (envioSelecionado.value?.resumo ?? null) as Record<
    string,
    unknown
  > | null;
  if (!r) return [];
  const h = r["histograma_erros"] as Record<string, number> | undefined;
  if (!h) return [];
  return Object.entries(h).sort((a, b) => b[1] - a[1]);
});

const itensFiltrados = computed<EstadoEnvioItem[]>(() => {
  if (!estado.value) return [];
  const q = filtroCpf.value.replace(/\D/g, "");
  if (!q) return estado.value.items;
  return estado.value.items.filter((i) => i.cpf.includes(q));
});

async function carregarMeses() {
  carregandoMeses.value = true;
  erroMeses.value = null;
  try {
    const r = await listarMesesTimeline(props.empresaId);
    meses.value = r.items;
    if (!perApurSel.value && r.items.length) {
      perApurSel.value = r.items[0].per_apur;
    }
  } catch (e: any) {
    erroMeses.value = e?.message ?? "falha ao listar meses";
  } finally {
    carregandoMeses.value = false;
  }
}

async function carregarRegua() {
  if (!perApurSel.value) return;
  carregandoRegua.value = true;
  try {
    regua.value = await reguaMes(props.empresaId, perApurSel.value);
    envioSelId.value = regua.value.timeline_mes.head_envio_id;
  } finally {
    carregandoRegua.value = false;
  }
}

async function carregarEstado() {
  if (!envioSelId.value) return;
  carregandoEstado.value = true;
  try {
    estado.value = await estadoEnvio(envioSelId.value);
  } finally {
    carregandoEstado.value = false;
  }
}

function fmtCPF(c: string) {
  const s = c.replace(/\D/g, "").padStart(11, "0");
  return `${s.slice(0, 3)}.${s.slice(3, 6)}.${s.slice(6, 9)}-${s.slice(9, 11)}`;
}

function statusIcon(s: string) {
  return (
    (
      {
        sucesso: "🟢",
        erro_esocial: "🔴",
        falha_rede: "🟡",
        rejeitado_local: "🟠",
        pendente: "⚪",
      } as Record<string, string>
    )[s] ?? "⚪"
  );
}

function onKey(e: KeyboardEvent) {
  if (!regua.value) return;
  if ((e.target as HTMLElement)?.tagName === "INPUT") return;
  const lst = [...regua.value.envios].sort((a, b) => a.sequencia - b.sequencia);
  const i = lst.findIndex((x) => x.id === envioSelId.value);
  if (e.key === "[" && i > 0) envioSelId.value = lst[i - 1].id;
  if (e.key === "]" && i >= 0 && i < lst.length - 1)
    envioSelId.value = lst[i + 1].id;
}

onMounted(() => {
  carregarMeses();
  window.addEventListener("keydown", onKey);
});

watch(perApurSel, carregarRegua);
watch(envioSelId, carregarEstado);

defineExpose({ recarregar: carregarMeses });
</script>

<template>
  <section class="cw">
    <header class="cw-head">
      <div>
        <h2>📜 Chain Walk — timeline mensal de S-1210</h2>
        <p>
          Cada bolinha é um envio. Versões antigas são imutáveis. HEAD é o
          estado atual.
        </p>
      </div>
      <div class="mes-sel">
        <label>perApur:</label>
        <select v-model="perApurSel" :disabled="!meses.length">
          <option v-if="!meses.length" :value="null">— sem dados —</option>
          <option v-for="m in meses" :key="m.id" :value="m.per_apur">
            {{ m.per_apur }} ({{ m.envios_total }} envio{{
              m.envios_total === 1 ? "" : "s"
            }})
          </option>
        </select>
      </div>
    </header>

    <div v-if="erroMeses" class="state err">{{ erroMeses }}</div>
    <div v-else-if="carregandoMeses" class="state">carregando…</div>
    <div v-else-if="!meses.length" class="state">
      Sem timeline ainda. Suba e extraia um zip do eSocial — a primeira régua
      aparece automaticamente.
    </div>

    <template v-else-if="regua">
      <TimelineRegua
        :envios="regua.envios"
        :selected-id="envioSelId"
        :head-id="regua.timeline_mes.head_envio_id"
        @select="(id) => (envioSelId = id)"
      />

      <div v-if="!isHead" class="banner-historico">
        📅 Você está olhando o estado de
        <strong
          >v{{
            regua.envios.find((e) => e.id === envioSelId)?.sequencia
          }}</strong
        >
        —
        <button
          class="lnk"
          @click="envioSelId = regua.timeline_mes.head_envio_id"
        >
          voltar pro AGORA
        </button>
      </div>

      <div v-if="explicacaoFalha" class="banner-falha">
        <div class="bf-head">
          <span class="bf-tag">⚠️ Lote rejeitado</span>
          <span v-if="ambienteReal" class="bf-amb"
            >ambiente: {{ ambienteReal }}</span
          >
          <span v-if="histogramaErros.length" class="bf-hist">
            <span
              v-for="[cod, n] in histogramaErros"
              :key="cod"
              class="bf-pill"
            >
              {{ cod }} × {{ n }}
            </span>
          </span>
        </div>
        <p class="bf-txt">{{ explicacaoFalha }}</p>
      </div>

      <div class="estado-envio liquid-glass">
        <div class="ee-head">
          <div class="totais" v-if="estado">
            <span class="t ok">🟢 {{ estado.totais.sucesso }}</span>
            <span class="t err">🔴 {{ estado.totais.erro_esocial }}</span>
            <span class="t warn">🟡 {{ estado.totais.falha_rede }}</span>
            <span class="t orange">🟠 {{ estado.totais.rejeitado_local }}</span>
          </div>
          <input
            v-model="filtroCpf"
            class="filtro"
            type="text"
            placeholder="filtrar CPF…"
          />
        </div>

        <div v-if="carregandoEstado" class="state">carregando estado…</div>
        <div v-else-if="estado" class="grid-cpfs">
          <button
            v-for="it in itensFiltrados.slice(0, 600)"
            :key="`${envioSelId}-${it.cpf}`"
            class="cpf-card"
            :class="it.status"
            @click="cpfSel = it.cpf"
          >
            <span class="ic">{{ statusIcon(it.status) }}</span>
            <span class="cpf-num mono">{{ fmtCPF(it.cpf) }}</span>
          </button>
          <div v-if="itensFiltrados.length > 600" class="hint">
            mostrando 600 de {{ itensFiltrados.length }} — refine o filtro
          </div>
          <div v-if="!itensFiltrados.length" class="hint">nenhum CPF</div>
        </div>
      </div>
    </template>

    <DrawerCadeiaCpf
      v-if="perApurSel"
      :empresa-id="empresaId"
      :cpf="cpfSel"
      :per-apur="perApurSel"
      @fechar="cpfSel = null"
    />
  </section>
</template>

<style scoped>
.cw {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.cw-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 10px;
}
.cw-head h2 {
  font-size: 1.05rem;
  color: #fff;
  margin: 0;
}
.cw-head p {
  font-size: 0.78rem;
  color: rgba(240, 209, 229, 0.6);
  margin: 4px 0 0;
}
.mes-sel {
  display: flex;
  align-items: center;
  gap: 8px;
}
.mes-sel label {
  font-size: 0.8rem;
  color: rgba(240, 209, 229, 0.7);
}
.mes-sel select {
  background: rgba(0, 0, 0, 0.4);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  padding: 6px 10px;
  font: inherit;
  font-size: 0.85rem;
  font-variant-numeric: tabular-nums;
}

.state {
  padding: 24px;
  text-align: center;
  color: rgba(240, 209, 229, 0.7);
  background: rgba(255, 255, 255, 0.03);
  border-radius: 14px;
}
.state.err {
  color: #ff8a8a;
}

.banner-historico {
  background: rgba(255, 200, 80, 0.1);
  border: 1px solid rgba(255, 200, 80, 0.35);
  color: #ffd47e;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.lnk {
  background: transparent;
  border: 1px solid rgba(255, 200, 80, 0.5);
  color: #ffd47e;
  padding: 4px 12px;
  border-radius: 8px;
  font: inherit;
  cursor: pointer;
}

.banner-falha {
  margin-top: 10px;
  background: rgba(255, 90, 90, 0.08);
  border: 1px solid rgba(255, 90, 90, 0.3);
  color: #ffbcbc;
  padding: 12px 14px;
  border-radius: 10px;
}
.banner-falha .bf-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.banner-falha .bf-tag {
  font-weight: 600;
  color: #ff8a8a;
  font-size: 0.85rem;
}
.banner-falha .bf-amb {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 0.72rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #f0d1e5;
}
.banner-falha .bf-hist {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-left: auto;
}
.banner-falha .bf-pill {
  background: rgba(255, 90, 90, 0.18);
  border: 1px solid rgba(255, 90, 90, 0.35);
  color: #ffd1d1;
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-variant-numeric: tabular-nums;
}
.banner-falha .bf-txt {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.5;
  color: rgba(255, 220, 220, 0.92);
}

.estado-envio {
  border-radius: 16px;
  padding: 16px 18px;
}
.ee-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.totais {
  display: flex;
  gap: 12px;
  font-size: 0.85rem;
  font-variant-numeric: tabular-nums;
}
.t.ok {
  color: #6dff7d;
}
.t.err {
  color: #ff8a8a;
}
.t.warn {
  color: #ffc966;
}
.t.orange {
  color: #ff9e5b;
}

.filtro {
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: #fff;
  padding: 6px 10px;
  border-radius: 8px;
  font: inherit;
  font-size: 0.85rem;
  width: 200px;
}

.grid-cpfs {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 6px;
  max-height: 460px;
  overflow-y: auto;
  padding-right: 4px;
}
.cpf-card {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 6px 10px;
  cursor: pointer;
  font: inherit;
  color: #fff;
  text-align: left;
  font-size: 0.78rem;
}
.cpf-card:hover {
  background: rgba(255, 255, 255, 0.07);
  border-color: rgba(255, 255, 255, 0.18);
}
.cpf-card.sucesso {
  border-color: rgba(61, 242, 75, 0.18);
}
.cpf-card.erro_esocial {
  border-color: rgba(255, 90, 90, 0.3);
}
.cpf-card.falha_rede {
  border-color: rgba(255, 200, 80, 0.3);
}
.cpf-card.rejeitado_local {
  border-color: rgba(255, 158, 91, 0.3);
}
.ic {
  font-size: 0.85rem;
}
.cpf-num {
  font-variant-numeric: tabular-nums;
}
.mono {
  font-family: ui-monospace, "Cascadia Code", monospace;
}
.hint {
  grid-column: 1 / -1;
  text-align: center;
  padding: 12px;
  color: rgba(240, 209, 229, 0.55);
  font-size: 0.82rem;
}
</style>
