<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  formatBytes,
  listarAtividade,
  type AtividadeRow,
} from "@/services/exploradorApi";

const props = defineProps<{ empresaId: number }>();

const items = ref<AtividadeRow[]>([]);
const carregando = ref(false);
const erro = ref<string | null>(null);

async function carregar() {
  carregando.value = true;
  erro.value = null;
  try {
    const r = await listarAtividade(props.empresaId, 200);
    items.value = r.items;
  } catch (e) {
    erro.value = (e as Error).message;
  } finally {
    carregando.value = false;
  }
}

defineExpose({ carregar });

onMounted(() => {
  carregar();
});

const stats = computed(() => {
  let uploads = 0;
  let exclusoes = 0;
  let extracoes = 0;
  let duplicados = 0;
  let bytesEnviados = 0;
  let bytesExcluidos = 0;
  for (const it of items.value) {
    if (it.acao === "upload") {
      uploads++;
      bytesEnviados += it.tamanho_bytes ?? 0;
    } else if (it.acao === "exclusao") {
      exclusoes++;
      bytesExcluidos += it.tamanho_bytes ?? 0;
    } else if (it.acao === "extracao") {
      extracoes++;
    } else if (it.acao === "duplicado") {
      duplicados++;
    }
  }
  return {
    uploads,
    exclusoes,
    extracoes,
    duplicados,
    bytesEnviados,
    bytesExcluidos,
  };
});

function fmtData(s: string): string {
  return new Date(s).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function rotulo(a: string) {
  switch (a) {
    case "upload":
      return { txt: "⬆ Upload", cls: "ok" };
    case "exclusao":
      return { txt: "🗑 Exclusão", cls: "err" };
    case "extracao":
      return { txt: "⚡ Extração", cls: "info" };
    case "duplicado":
      return { txt: "= Duplicado", cls: "warn" };
    default:
      return { txt: a, cls: "neutral" };
  }
}

function detalheCurto(it: AtividadeRow): string {
  if (!it.detalhe) return "";
  const d = it.detalhe as Record<string, unknown>;
  const partes: string[] = [];
  if (typeof d.indexados === "number") partes.push(`${d.indexados} indexados`);
  if (typeof d.falhas === "number" && d.falhas)
    partes.push(`${d.falhas} falhas`);
  if (typeof d.eventos_apagados === "number")
    partes.push(`${d.eventos_apagados} eventos apagados`);
  if (typeof d.perapur_dominante === "string" && d.perapur_dominante)
    partes.push(`perApur ${d.perapur_dominante}`);
  return partes.join(" · ");
}
</script>

<template>
  <section class="hist liquid-glass">
    <header class="hist-head">
      <div>
        <h3 class="hist-title gg-glow">📜 Histórico de atividade</h3>
        <p class="hist-sub">
          Tudo que foi enviado, extraído ou excluído fica registrado aqui.
        </p>
      </div>
      <button class="btn-ghost" :disabled="carregando" @click="carregar">
        {{ carregando ? "…" : "↻ atualizar" }}
      </button>
    </header>

    <div class="stats">
      <div class="stat">
        <div class="stat-num accent">{{ stats.uploads }}</div>
        <div class="stat-lbl">Uploads</div>
      </div>
      <div class="stat">
        <div class="stat-num">{{ formatBytes(stats.bytesEnviados) }}</div>
        <div class="stat-lbl">Enviado total</div>
      </div>
      <div class="stat">
        <div class="stat-num err">{{ stats.exclusoes }}</div>
        <div class="stat-lbl">Exclusões</div>
      </div>
      <div class="stat">
        <div class="stat-num">{{ formatBytes(stats.bytesExcluidos) }}</div>
        <div class="stat-lbl">Liberado</div>
      </div>
      <div class="stat">
        <div class="stat-num">{{ stats.extracoes }}</div>
        <div class="stat-lbl">Extrações</div>
      </div>
      <div class="stat">
        <div class="stat-num warn">{{ stats.duplicados }}</div>
        <div class="stat-lbl">Duplicados</div>
      </div>
    </div>

    <div v-if="erro" class="err-msg">⚠ {{ erro }}</div>

    <div v-if="items.length === 0 && !carregando" class="empty">
      Nenhum evento registrado ainda.
    </div>

    <ol v-else class="timeline">
      <li v-for="it in items" :key="it.id" class="row">
        <span class="badge" :class="rotulo(it.acao).cls">
          {{ rotulo(it.acao).txt }}
        </span>
        <div class="info">
          <div class="line1">
            <span class="nome">{{ it.nome_arquivo ?? "—" }}</span>
            <span v-if="it.tamanho_bytes" class="meta">
              · {{ formatBytes(it.tamanho_bytes) }}
            </span>
            <span v-if="it.total_xmls" class="meta">
              · {{ it.total_xmls }} XMLs
            </span>
          </div>
          <div class="line2">
            <span class="data mono">{{ fmtData(it.criado_em) }}</span>
            <span v-if="detalheCurto(it)" class="det">{{
              detalheCurto(it)
            }}</span>
          </div>
        </div>
      </li>
    </ol>
  </section>
</template>

<style scoped>
.hist {
  border-radius: 18px;
  padding: 22px;
}
.hist-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
  gap: 12px;
}
.hist-title {
  margin: 0;
  font-size: 1.15rem;
  color: #fff;
}
.hist-sub {
  margin: 4px 0 0;
  font-size: 0.85rem;
  color: rgba(240, 209, 229, 0.65);
}

.btn-ghost {
  background: transparent;
  color: #f0d1e5;
  border: 1px solid rgba(240, 209, 229, 0.25);
  border-radius: 10px;
  padding: 6px 12px;
  cursor: pointer;
  font: inherit;
}
.btn-ghost:hover {
  border-color: rgba(240, 209, 229, 0.5);
}

.stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
  margin-bottom: 18px;
}
.stat {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  padding: 10px 12px;
}
.stat-num {
  font-size: 1.4rem;
  font-weight: 700;
  color: #fff;
  font-variant-numeric: tabular-nums;
}
.stat-num.accent {
  color: #3df24b;
}
.stat-num.err {
  color: #ff8a8a;
}
.stat-num.warn {
  color: #ffd17a;
}
.stat-lbl {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: rgba(240, 209, 229, 0.55);
  margin-top: 2px;
}

.empty {
  padding: 30px 12px;
  text-align: center;
  color: rgba(240, 209, 229, 0.55);
}

.err-msg {
  background: rgba(255, 70, 70, 0.08);
  border: 1px solid rgba(255, 70, 70, 0.3);
  color: #ff8a8a;
  padding: 8px 12px;
  border-radius: 10px;
  margin-bottom: 12px;
}

.timeline {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 480px;
  overflow-y: auto;
}
.row {
  display: grid;
  grid-template-columns: 130px 1fr;
  gap: 12px;
  align-items: start;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid transparent;
  transition: background 120ms;
}
.row:hover {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255, 255, 255, 0.05);
}

.badge {
  display: inline-block;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-radius: 999px;
  padding: 4px 10px;
  text-align: center;
  font-weight: 600;
}
.badge.ok {
  background: rgba(61, 242, 75, 0.14);
  color: #6dff7d;
  border: 1px solid rgba(61, 242, 75, 0.4);
}
.badge.err {
  background: rgba(255, 80, 80, 0.12);
  color: #ff8a8a;
  border: 1px solid rgba(255, 80, 80, 0.4);
}
.badge.info {
  background: rgba(120, 180, 255, 0.12);
  color: #9cc6ff;
  border: 1px solid rgba(120, 180, 255, 0.4);
}
.badge.warn {
  background: rgba(255, 200, 80, 0.12);
  color: #ffd17a;
  border: 1px solid rgba(255, 200, 80, 0.4);
}

.info .line1 {
  color: #fff;
  font-size: 0.92rem;
}
.nome {
  font-weight: 600;
}
.meta {
  color: rgba(240, 209, 229, 0.65);
  font-size: 0.82rem;
}
.line2 {
  display: flex;
  gap: 12px;
  margin-top: 2px;
  font-size: 0.78rem;
  color: rgba(240, 209, 229, 0.55);
}
.mono {
  font-family: ui-monospace, "Cascadia Code", monospace;
}
</style>
