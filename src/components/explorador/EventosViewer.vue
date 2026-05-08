<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import {
  resumoZip,
  CATEGORIAS,
  categoriaDoTipo,
  type ResumoZip,
  type ZipRow,
  type CategoriaEvento,
} from "@/services/exploradorApi";
import EventosLista from "./EventosLista.vue";

const props = defineProps<{ zip: ZipRow }>();
const emit = defineEmits<{ (e: "fechar"): void }>();

const loading = ref(true);
const erro = ref<string | null>(null);
const resumo = ref<ResumoZip | null>(null);

// quando user clica numa pasta de tipo específico
const tipoFiltrado = ref<string | null>(null);
// drill por categoria (mostra grid filtrado dentro da categoria)
const categoriaAberta = ref<string | null>(null);

async function carregar() {
  loading.value = true;
  erro.value = null;
  try {
    resumo.value = await resumoZip(props.zip.id);
  } catch (e) {
    erro.value = (e as Error).message;
  } finally {
    loading.value = false;
  }
}

onMounted(carregar);
watch(() => props.zip.id, carregar);

interface PastaTipo {
  tipo: string;
  count: number;
  cat: CategoriaEvento;
}

interface PastaCategoria {
  cat: CategoriaEvento;
  total: number;
  tipos: PastaTipo[];
}

const pastasPorCategoria = computed<PastaCategoria[]>(() => {
  if (!resumo.value) return [];
  const buckets = new Map<string, PastaCategoria>();
  for (const c of CATEGORIAS) {
    buckets.set(c.id, { cat: c, total: 0, tipos: [] });
  }
  for (const r of resumo.value.por_tipo) {
    const cat = categoriaDoTipo(r.tipo_evento);
    const b = buckets.get(cat.id)!;
    b.total += r.n;
    b.tipos.push({ tipo: r.tipo_evento, count: r.n, cat });
  }
  return Array.from(buckets.values())
    .filter((b) => b.total > 0)
    .map((b) => ({
      ...b,
      tipos: b.tipos.sort((a, b) => b.count - a.count),
    }))
    .sort((a, b) => b.total - a.total);
});

const totalEventos = computed(
  () => resumo.value?.por_tipo.reduce((s, r) => s + r.n, 0) ?? 0,
);

const periodos = computed(
  () => resumo.value?.por_per_apur.map((p) => p.per_apur) ?? [],
);

function abrirTipo(tipo: string) {
  tipoFiltrado.value = tipo;
}

function voltarParaPastas() {
  tipoFiltrado.value = null;
  categoriaAberta.value = null;
}

function abrirCategoria(catId: string) {
  if (categoriaAberta.value === catId) categoriaAberta.value = null;
  else categoriaAberta.value = catId;
}

function fmtPeriodo() {
  const a = props.zip.dt_ini.slice(0, 7);
  const b = props.zip.dt_fim.slice(0, 7);
  return a === b ? a : `${a} → ${b}`;
}
</script>

<template>
  <div class="viewer">
    <header class="viewer-head">
      <div class="vh-left">
        <button class="btn-back" @click="emit('fechar')">← voltar</button>
        <div class="vh-title">
          <div class="t1 gg-glow">{{ fmtPeriodo() }}</div>
          <div class="t2">{{ zip.nome_arquivo_original }}</div>
        </div>
      </div>
      <div class="vh-stats">
        <div class="stat">
          <span class="n">{{ totalEventos.toLocaleString("pt-BR") }}</span>
          <span class="l">eventos</span>
        </div>
        <div class="stat">
          <span class="n">{{ resumo?.cpfs_distintos ?? 0 }}</span>
          <span class="l">CPFs</span>
        </div>
        <div class="stat">
          <span class="n">{{ periodos.length }}</span>
          <span class="l">{{
            periodos.length === 1 ? "período" : "períodos"
          }}</span>
        </div>
      </div>
    </header>

    <!-- Modo drill: mostra lista de eventos do tipo escolhido -->
    <div v-if="tipoFiltrado" class="drill">
      <div class="drill-bar">
        <button class="btn-back" @click="voltarParaPastas">
          ← todas as pastas
        </button>
        <div class="drill-title">
          <span
            class="tipo-tag"
            :style="{
              background: `hsla(${categoriaDoTipo(tipoFiltrado).cor} / 0.18)`,
              borderColor: `hsla(${categoriaDoTipo(tipoFiltrado).cor} / 0.5)`,
            }"
          >
            {{ categoriaDoTipo(tipoFiltrado).icone }} {{ tipoFiltrado }}
          </span>
        </div>
      </div>
      <EventosLista
        :empresa-id="zip.empresa_id"
        :zip-id="zip.id"
        :tipo-evento="tipoFiltrado"
      />
    </div>

    <!-- Loading / erro / pastas -->
    <div v-else-if="loading" class="loading">
      <div class="spinner"></div>
      Carregando resumo do zip…
    </div>
    <div v-else-if="erro" class="error">⚠ {{ erro }}</div>

    <div v-else class="cats">
      <div
        v-for="b in pastasPorCategoria"
        :key="b.cat.id"
        class="cat-block liquid-glass"
        :style="{
          '--cat-color': `hsl(${b.cat.cor})`,
          '--cat-color-soft': `hsla(${b.cat.cor} / 0.14)`,
          '--cat-color-border': `hsla(${b.cat.cor} / 0.45)`,
        }"
      >
        <div class="cat-head" @click="abrirCategoria(b.cat.id)">
          <div class="cat-icon">{{ b.cat.icone }}</div>
          <div class="cat-title">
            <div class="ct1">{{ b.cat.titulo }}</div>
            <div class="ct2">{{ b.cat.descricao }}</div>
          </div>
          <div class="cat-total">
            <div class="ctn">{{ b.total.toLocaleString("pt-BR") }}</div>
            <div class="ctl">eventos</div>
          </div>
          <div
            class="cat-arrow"
            :class="{
              open:
                categoriaAberta === b.cat.id || pastasPorCategoria.length <= 2,
            }"
          >
            ▾
          </div>
        </div>

        <div
          class="cat-pastas"
          v-show="
            categoriaAberta === b.cat.id || pastasPorCategoria.length <= 2
          "
        >
          <div
            v-for="t in b.tipos"
            :key="t.tipo"
            class="pasta"
            @click="abrirTipo(t.tipo)"
          >
            <div class="folder">
              <div class="folder-tab"></div>
              <div class="folder-body">
                <div class="folder-icon">{{ b.cat.icone }}</div>
                <div class="folder-tipo">{{ t.tipo }}</div>
                <div class="folder-count">
                  {{ t.count.toLocaleString("pt-BR") }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.viewer {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.viewer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  flex-wrap: wrap;
  padding: 14px 18px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(240, 209, 229, 0.1);
}
.vh-left {
  display: flex;
  align-items: center;
  gap: 14px;
}
.btn-back {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(240, 209, 229, 0.2);
  color: #fff;
  border-radius: 8px;
  padding: 7px 13px;
  cursor: pointer;
  font: inherit;
}
.btn-back:hover {
  border-color: rgba(61, 242, 75, 0.5);
}
.vh-title .t1 {
  font-size: 1.3rem;
  font-weight: 700;
  color: #fff;
}
.vh-title .t2 {
  font-size: 0.8rem;
  color: rgba(240, 209, 229, 0.6);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  margin-top: 2px;
}

.vh-stats {
  display: flex;
  gap: 16px;
}
.stat {
  text-align: right;
  padding: 6px 14px;
  border-radius: 10px;
  background: rgba(61, 242, 75, 0.05);
  border: 1px solid rgba(61, 242, 75, 0.2);
}
.stat .n {
  display: block;
  font-size: 1.4rem;
  font-weight: 700;
  color: #3df24b;
  text-shadow: 0 0 10px rgba(61, 242, 75, 0.4);
  font-variant-numeric: tabular-nums;
}
.stat .l {
  font-size: 0.7rem;
  color: rgba(240, 209, 229, 0.7);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.cats {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.cat-block {
  border-radius: 16px;
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--cat-color-border);
}

.cat-head {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  cursor: pointer;
  background: var(--cat-color-soft);
  transition: background 160ms ease;
}
.cat-head:hover {
  background: color-mix(in srgb, var(--cat-color) 18%, transparent);
}
.cat-icon {
  font-size: 2.2rem;
  filter: drop-shadow(0 0 8px var(--cat-color));
}
.cat-title {
  flex: 1;
}
.ct1 {
  font-size: 1.15rem;
  font-weight: 700;
  color: #fff;
}
.ct2 {
  font-size: 0.85rem;
  color: rgba(240, 209, 229, 0.7);
  margin-top: 2px;
}
.cat-total {
  text-align: right;
}
.ctn {
  font-size: 1.6rem;
  font-weight: 800;
  color: var(--cat-color);
  text-shadow: 0 0 10px var(--cat-color);
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
.ctl {
  font-size: 0.7rem;
  color: rgba(240, 209, 229, 0.6);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-top: 4px;
}
.cat-arrow {
  font-size: 1.3rem;
  color: rgba(240, 209, 229, 0.5);
  transition: transform 200ms ease;
}
.cat-arrow.open {
  transform: rotate(180deg);
}

.cat-pastas {
  padding: 18px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 14px;
  border-top: 1px solid rgba(240, 209, 229, 0.08);
}

.pasta {
  cursor: pointer;
  transition: transform 180ms ease;
}
.pasta:hover {
  transform: translateY(-3px);
}

/* Pasta visual estilo "manila folder" */
.folder {
  position: relative;
  border-radius: 10px;
  padding-top: 10px;
  filter: drop-shadow(0 4px 14px rgba(0, 0, 0, 0.35));
}
.folder-tab {
  position: absolute;
  top: 0;
  left: 12px;
  width: 56px;
  height: 14px;
  background: var(--cat-color);
  border-radius: 6px 6px 0 0;
  opacity: 0.85;
  box-shadow: 0 0 10px var(--cat-color);
}
.folder-body {
  background: linear-gradient(
    160deg,
    color-mix(in srgb, var(--cat-color) 24%, #0d1417) 0%,
    color-mix(in srgb, var(--cat-color) 8%, #0d1417) 100%
  );
  border: 1px solid var(--cat-color-border);
  border-radius: 4px 10px 10px 10px;
  padding: 14px 12px 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  position: relative;
  overflow: hidden;
}
.folder-body::before {
  content: "";
  position: absolute;
  inset: 0;
  background: radial-gradient(
    circle at 50% 0%,
    color-mix(in srgb, var(--cat-color) 20%, transparent) 0%,
    transparent 60%
  );
  opacity: 0.6;
  pointer-events: none;
}
.folder-icon {
  font-size: 1.6rem;
  margin-bottom: 2px;
}
.folder-tipo {
  font-weight: 700;
  color: #fff;
  font-size: 0.95rem;
  letter-spacing: 0.02em;
  position: relative;
}
.folder-count {
  font-size: 1.5rem;
  font-weight: 800;
  color: var(--cat-color);
  text-shadow: 0 0 10px var(--cat-color);
  font-variant-numeric: tabular-nums;
  position: relative;
}

.pasta:hover .folder-body {
  border-color: var(--cat-color);
  box-shadow: inset 0 0 18px
    color-mix(in srgb, var(--cat-color) 18%, transparent);
}

.loading,
.error {
  text-align: center;
  padding: 40px;
  color: rgba(240, 209, 229, 0.7);
}
.error {
  color: #ffb3b3;
}
.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(61, 242, 75, 0.15);
  border-top-color: #3df24b;
  border-radius: 50%;
  margin: 0 auto 12px;
  animation: spin 900ms linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.drill {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.drill-bar {
  display: flex;
  align-items: center;
  gap: 14px;
}
.tipo-tag {
  border: 1px solid;
  border-radius: 999px;
  padding: 6px 14px;
  color: #fff;
  font-weight: 700;
  font-size: 0.95rem;
}
</style>
