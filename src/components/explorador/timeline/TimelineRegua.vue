<script setup lang="ts">
import { computed, ref } from "vue";
import type { TimelineEnvio } from "@/services/exploradorApi";

const props = defineProps<{
  envios: TimelineEnvio[];
  selectedId: number | null;
  headId: number | null;
}>();
const emit = defineEmits<{
  (e: "select", envioId: number): void;
}>();

const lista = computed(() =>
  [...props.envios].sort((a, b) => a.sequencia - b.sequencia),
);

// Agrupa envios consecutivos sem sucesso (zip_inicial sempre fica fora) em "rounds".
// Cada round colapsado vira 1 bolinha; o usuario pode expandir para ver v1..vN.
type ItemReg =
  | { kind: "single"; env: TimelineEnvio }
  | {
      kind: "round";
      key: string;
      envs: TimelineEnvio[];
      totalErro: number;
      seqIni: number;
      seqFim: number;
    };

const rounds = computed<ItemReg[]>(() => {
  const out: ItemReg[] = [];
  let buf: TimelineEnvio[] = [];
  const flushBuf = () => {
    if (buf.length === 0) return;
    const first = buf[0];
    const last = buf[buf.length - 1];
    if (!first || !last) return;
    if (buf.length === 1) {
      out.push({ kind: "single", env: first });
    } else {
      out.push({
        kind: "round",
        key: `round-${first.sequencia}-${last.sequencia}`,
        envs: [...buf],
        totalErro: buf.reduce((s, e) => s + (e.total_erro || 0), 0),
        seqIni: first.sequencia,
        seqFim: last.sequencia,
      });
    }
    buf = [];
  };
  for (const e of lista.value) {
    const isFalhaPura =
      e.tipo !== "zip_inicial" &&
      (e.total_sucesso || 0) === 0 &&
      (e.total_erro || 0) > 0;
    if (isFalhaPura) {
      buf.push(e);
    } else {
      flushBuf();
      out.push({ kind: "single", env: e });
    }
  }
  flushBuf();
  return out;
});

// Rounds expandidos por chave
const expandidos = ref<Set<string>>(new Set());
function toggleRound(key: string) {
  const s = new Set(expandidos.value);
  if (s.has(key)) s.delete(key);
  else s.add(key);
  expandidos.value = s;
}

function fmtData(s: string | null) {
  if (!s) return "—";
  return new Date(s).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function rotuloTipo(t: string) {
  if (t === "zip_inicial") return "estado inicial";
  if (t === "envio_massa") return "envio em massa";
  if (t === "envio_individual") return "envio individual";
  return t;
}

function corBolinha(env: TimelineEnvio): string {
  if (env.status === "em_andamento") return "warn";
  if (env.status === "falhou") return "err";
  if (env.tipo === "zip_inicial") return "init";
  if (env.total_erro > 0 && env.total_sucesso > 0) return "mixed";
  if (env.total_erro > 0) return "err";
  return "ok";
}

function indexAtual(): number {
  return lista.value.findIndex((e) => e.id === props.selectedId);
}

function avancar() {
  const i = indexAtual();
  const next = lista.value[i + 1];
  if (i >= 0 && i < lista.value.length - 1 && next) emit("select", next.id);
}
function voltar() {
  const i = indexAtual();
  const prev = lista.value[i - 1];
  if (i > 0 && prev) emit("select", prev.id);
}
function irParaHead() {
  if (props.headId) emit("select", props.headId);
}

const isHead = computed(() => props.selectedId === props.headId);
</script>

<template>
  <div class="regua liquid-glass">
    <div class="regua-head">
      <div class="title">📜 Linha do tempo de envios</div>
      <div class="actions">
        <button
          class="nav"
          :disabled="indexAtual() <= 0"
          @click="voltar"
          title="◀ envio anterior"
        >
          ◀
        </button>
        <button
          class="nav"
          :disabled="indexAtual() >= lista.length - 1"
          @click="avancar"
          title="próximo envio ▶"
        >
          ▶
        </button>
        <button
          class="agora"
          :class="{ active: isHead }"
          @click="irParaHead"
          :disabled="isHead"
        >
          {{ isHead ? "● AGORA" : "↻ ir para AGORA" }}
        </button>
      </div>
    </div>

    <div class="trilho">
      <template
        v-for="(item, idx) in rounds"
        :key="item.kind === 'round' ? item.key : item.env.id"
      >
        <!-- Envio individual -->
        <div
          v-if="item.kind === 'single'"
          class="ponto-wrap"
          :class="{ selected: item.env.id === selectedId }"
        >
          <div
            v-if="idx > 0"
            class="conector"
            :class="corBolinha(item.env)"
          ></div>
          <button
            class="ponto"
            :class="corBolinha(item.env)"
            @click="emit('select', item.env.id)"
          >
            <div class="seq">v{{ item.env.sequencia }}</div>
          </button>
          <div class="legenda">
            <div class="lbl">{{ rotuloTipo(item.env.tipo) }}</div>
            <div class="data mono">{{ fmtData(item.env.iniciado_em) }}</div>
            <div class="contadores">
              <span v-if="item.env.total_sucesso" class="ok-num"
                >+{{ item.env.total_sucesso }}</span
              >
              <span v-if="item.env.total_erro" class="err-num"
                >{{ item.env.total_erro }} erro</span
              >
              <span v-if="item.env.id === headId" class="head-tag">HEAD</span>
            </div>
          </div>
        </div>

        <!-- Round colapsado: clique pra expandir -->
        <div
          v-else-if="!expandidos.has(item.key)"
          class="ponto-wrap round"
          :class="{ selected: item.envs.some((e) => e.id === selectedId) }"
        >
          <div v-if="idx > 0" class="conector err"></div>
          <button class="ponto round err" @click="toggleRound(item.key)">
            <div class="round-label">×{{ item.envs.length }}</div>
          </button>
          <div class="legenda">
            <div class="lbl round-lbl">▶ tentativas falhadas</div>
            <div class="data mono">v{{ item.seqIni }}–v{{ item.seqFim }}</div>
            <div class="contadores">
              <span class="err-num">{{ item.totalErro }} erro</span>
            </div>
          </div>
        </div>

        <!-- Round expandido: render todos os v internos -->
        <template v-else>
          <div class="ponto-wrap round-toggle" :key="item.key + '-toggle'">
            <div v-if="idx > 0" class="conector err"></div>
            <button
              class="ponto round-collapse"
              @click="toggleRound(item.key)"
              title="recolher"
            >
              <div class="round-label">▾</div>
            </button>
            <div class="legenda">
              <div class="lbl round-lbl">tentativas (clique p/ recolher)</div>
            </div>
          </div>
          <div
            v-for="env in item.envs"
            :key="env.id"
            class="ponto-wrap"
            :class="{ selected: env.id === selectedId, 'in-round': true }"
          >
            <div class="conector" :class="corBolinha(env)"></div>
            <button
              class="ponto"
              :class="corBolinha(env)"
              @click="emit('select', env.id)"
            >
              <div class="seq">v{{ env.sequencia }}</div>
            </button>
            <div class="legenda">
              <div class="lbl">{{ rotuloTipo(env.tipo) }}</div>
              <div class="data mono">{{ fmtData(env.iniciado_em) }}</div>
              <div class="contadores">
                <span v-if="env.total_sucesso" class="ok-num"
                  >+{{ env.total_sucesso }}</span
                >
                <span v-if="env.total_erro" class="err-num"
                  >{{ env.total_erro }} erro</span
                >
              </div>
            </div>
          </div>
        </template>
      </template>
    </div>
  </div>
</template>

<style scoped>
.regua {
  border-radius: 18px;
  padding: 18px 22px;
}
.regua-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.title {
  font-size: 1.05rem;
  font-weight: 600;
  color: #fff;
}
.actions {
  display: flex;
  gap: 6px;
}
.nav,
.agora {
  background: rgba(255, 255, 255, 0.04);
  color: #f0d1e5;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 6px 12px;
  cursor: pointer;
  font: inherit;
  font-size: 0.85rem;
}
.nav:disabled,
.agora:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.agora.active {
  border-color: rgba(61, 242, 75, 0.5);
  color: #6dff7d;
  background: rgba(61, 242, 75, 0.08);
}

.trilho {
  display: flex;
  align-items: flex-start;
  gap: 0;
  overflow-x: auto;
  padding: 8px 0 4px;
}

.ponto-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  position: relative;
  min-width: 110px;
}
.ponto-wrap .conector {
  position: absolute;
  top: 22px;
  right: 50%;
  width: 100%;
  height: 2px;
  background: rgba(255, 255, 255, 0.15);
  z-index: 0;
}
.ponto-wrap .conector.ok {
  background: rgba(61, 242, 75, 0.4);
}
.ponto-wrap .conector.err {
  background: rgba(255, 90, 90, 0.4);
}
.ponto-wrap .conector.warn {
  background: rgba(255, 200, 80, 0.4);
}
.ponto-wrap .conector.mixed {
  background: linear-gradient(
    90deg,
    rgba(255, 90, 90, 0.4),
    rgba(61, 242, 75, 0.4)
  );
}
.ponto-wrap .conector.init {
  background: rgba(140, 180, 255, 0.35);
}

.ponto {
  position: relative;
  z-index: 1;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: 2px solid;
  background: rgba(0, 0, 0, 0.4);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font: inherit;
  color: #fff;
  transition:
    transform 120ms,
    box-shadow 120ms;
}
.ponto:hover {
  transform: scale(1.1);
}
.ponto.ok {
  border-color: #3df24b;
  box-shadow: 0 0 12px rgba(61, 242, 75, 0.5);
}
.ponto.err {
  border-color: #ff6b6b;
  box-shadow: 0 0 12px rgba(255, 90, 90, 0.4);
}
.ponto.warn {
  border-color: #ffc966;
  box-shadow: 0 0 12px rgba(255, 200, 80, 0.4);
}
.ponto.mixed {
  border-color: #ffc966;
  box-shadow: 0 0 12px rgba(255, 160, 80, 0.4);
}
.ponto.init {
  border-color: #8cb4ff;
  box-shadow: 0 0 12px rgba(140, 180, 255, 0.4);
}

.ponto-wrap.selected .ponto {
  transform: scale(1.2);
  box-shadow: 0 0 18px currentColor;
}

.seq {
  font-size: 0.75rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.legenda {
  margin-top: 8px;
  text-align: center;
  font-size: 0.72rem;
}
.lbl {
  color: rgba(240, 209, 229, 0.75);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.data {
  color: #fff;
  margin-top: 2px;
}
.contadores {
  display: flex;
  justify-content: center;
  gap: 6px;
  margin-top: 4px;
  flex-wrap: wrap;
}
.ok-num {
  color: #6dff7d;
}
.err-num {
  color: #ff8a8a;
}
.head-tag {
  background: rgba(61, 242, 75, 0.18);
  color: #6dff7d;
  border: 1px solid rgba(61, 242, 75, 0.45);
  padding: 1px 6px;
  border-radius: 999px;
  font-weight: 700;
  font-size: 0.62rem;
  letter-spacing: 0.06em;
}
.mono {
  font-family: ui-monospace, "Cascadia Code", monospace;
}

/* Round colapsado / expansor */
.ponto.round {
  width: 56px;
  height: 56px;
  border-style: dashed;
  background: rgba(255, 90, 90, 0.08);
}
.round-label {
  font-size: 0.95rem;
  font-weight: 700;
}
.round-lbl {
  color: rgba(255, 138, 138, 0.85);
}
.ponto.round-collapse {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.25);
  border-style: dashed;
  width: 36px;
  height: 36px;
}
.ponto-wrap.round-toggle {
  min-width: 70px;
  align-self: center;
}
.ponto-wrap.in-round .ponto {
  width: 34px;
  height: 34px;
  opacity: 0.78;
}
.ponto-wrap.in-round.selected .ponto {
  opacity: 1;
}
.ponto-wrap.in-round .legenda .data,
.ponto-wrap.in-round .legenda .lbl {
  font-size: 0.62rem;
}
.ponto-wrap.in-round {
  min-width: 78px;
}
</style>
