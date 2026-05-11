<script setup lang="ts">
import { computed, ref } from "vue";
import {
  formatBytes,
  urlDownloadZip,
  extrairZip,
  deletarZip,
  type ZipRow,
} from "@/services/exploradorApi";

const props = defineProps<{ zips: ZipRow[]; empresaId?: number }>();
const emit = defineEmits<{
  (e: "visualizar", zip: ZipRow): void;
  (e: "refresh"): void;
}>();

const extraindo = ref<Set<number>>(new Set());
const extracaoErro = ref<Map<number, string>>(new Map());
const excluindo = ref<Set<number>>(new Set());

async function disparaExtracao(z: ZipRow) {
  extraindo.value.add(z.id);
  extracaoErro.value.delete(z.id);
  // força reatividade
  extraindo.value = new Set(extraindo.value);
  try {
    await extrairZip(z.id, { empresaId: props.empresaId });
    emit("refresh");
  } catch (e) {
    extracaoErro.value.set(z.id, (e as Error).message);
    extracaoErro.value = new Map(extracaoErro.value);
  } finally {
    extraindo.value.delete(z.id);
    extraindo.value = new Set(extraindo.value);
  }
}

async function disparaReextrairS5002(z: ZipRow) {
  const ok = window.confirm(
    `Re-extrair APENAS S-5002 deste zip?\n\n` +
      `• ${z.nome_arquivo_original}\n` +
      `• ${z.perapur_dominante ?? z.dt_ini.slice(0, 7)}\n\n` +
      `Os eventos S-1210 NÃO serão tocados (nem inseridos, nem ` +
      `atualizados). Apenas o dados_json dos S-5002 será enriquecido ` +
      `com infoIR e totais consolidados.`,
  );
  if (!ok) return;
  extraindo.value.add(z.id);
  extracaoErro.value.delete(z.id);
  extraindo.value = new Set(extraindo.value);
  try {
    await extrairZip(z.id, {
      somenteS5002: true,
      empresaId: props.empresaId,
    });
    emit("refresh");
  } catch (e) {
    extracaoErro.value.set(z.id, (e as Error).message);
    extracaoErro.value = new Map(extracaoErro.value);
  } finally {
    extraindo.value.delete(z.id);
    extraindo.value = new Set(extraindo.value);
  }
}

async function disparaExclusao(z: ZipRow) {
  const ok = window.confirm(
    `Excluir definitivamente este zip?\n\n` +
      `• ${z.nome_arquivo_original}\n` +
      `• ${formatBytes(z.tamanho_bytes)}\n` +
      `• ${z.total_xmls ?? 0} eventos indexados\n\n` +
      `Vai apagar o arquivo, os XMLs indexados e liberar espaço.\n` +
      `(O histórico desta exclusão fica registrado.)`,
  );
  if (!ok) return;
  excluindo.value.add(z.id);
  excluindo.value = new Set(excluindo.value);
  try {
    await deletarZip(z.id);
    emit("refresh");
  } catch (e) {
    window.alert(`Falha ao excluir: ${(e as Error).message}`);
  } finally {
    excluindo.value.delete(z.id);
    excluindo.value = new Set(excluindo.value);
  }
}

function fmtPeriodo(z: ZipRow) {
  const a = z.dt_ini.slice(0, 7);
  const b = z.dt_fim.slice(0, 7);
  return a === b ? a : `${a} → ${b}`;
}

function fmtData(s: string | null): string {
  if (!s) return "—";
  return new Date(s).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function statusLabel(s: string) {
  if (s === "ok") return { label: "indexado", cls: "ok" };
  if (s === "extraindo") return { label: "extraindo…", cls: "warn" };
  if (s === "pendente") return { label: "pendente", cls: "warn" };
  if (s === "erro") return { label: "erro", cls: "err" };
  return { label: s, cls: "neutral" };
}

const zipsOrdenados = computed(() =>
  [...props.zips].sort((a, b) => b.enviado_em.localeCompare(a.enviado_em)),
);
</script>

<template>
  <div v-if="zips.length === 0" class="empty liquid-glass">
    <div class="empty-icon">📁</div>
    <div class="empty-title">Nenhum zip enviado ainda</div>
    <div class="empty-sub">Suba o primeiro arquivo acima para começar.</div>
  </div>

  <div v-else class="grid">
    <div v-for="z in zipsOrdenados" :key="z.id" class="zip-card liquid-glass">
      <div class="zc-head">
        <div class="zc-period gg-glow">{{ fmtPeriodo(z) }}</div>
        <span class="badge" :class="statusLabel(z.extracao_status).cls">
          {{ statusLabel(z.extracao_status).label }}
        </span>
      </div>

      <div class="zc-name" :title="z.nome_arquivo_original">
        {{ z.nome_arquivo_original }}
      </div>

      <div class="zc-meta">
        <div>
          <span class="lbl">Tamanho</span>
          <span class="val mono">{{ formatBytes(z.tamanho_bytes) }}</span>
        </div>
        <div>
          <span class="lbl">XMLs</span>
          <span class="val mono accent">{{ z.total_xmls ?? "—" }}</span>
        </div>
        <div>
          <span class="lbl">PerApur</span>
          <span class="val mono">{{ z.perapur_dominante ?? "—" }}</span>
        </div>
        <div>
          <span class="lbl">Enviado</span>
          <span class="val mono">{{ fmtData(z.enviado_em) }}</span>
        </div>
      </div>

      <div
        v-if="z.extracao_status === 'erro' && z.extracao_erro"
        class="err-msg"
      >
        ⚠ {{ z.extracao_erro }}
      </div>
      <div v-if="extracaoErro.get(z.id)" class="err-msg">
        ⚠ {{ extracaoErro.get(z.id) }}
      </div>

      <div class="zc-actions">
        <button
          v-if="
            z.extracao_status === 'pendente' || z.extracao_status === 'erro'
          "
          class="btn-primary"
          :disabled="extraindo.has(z.id)"
          @click="disparaExtracao(z)"
        >
          {{
            extraindo.has(z.id)
              ? "… extraindo (pode demorar)"
              : "⚡ Extrair agora"
          }}
        </button>
        <button
          v-else-if="z.extracao_status === 'extraindo'"
          class="btn-primary"
          disabled
        >
          … extraindo…
        </button>
        <button
          v-else
          class="btn-primary"
          :disabled="z.extracao_status !== 'ok'"
          @click="emit('visualizar', z)"
        >
          🔍 Visualizar eventos
        </button>
        <a class="btn-ghost" :href="urlDownloadZip(z.id)" download>
          ⬇ Baixar zip
        </a>
        <button
          v-if="z.extracao_status === 'ok'"
          class="btn-ghost"
          :disabled="extraindo.has(z.id)"
          @click="disparaReextrairS5002(z)"
          :title="'Reextrai apenas S-5002 (não toca S-1210). Útil para mês já enviado.'"
        >
          {{ extraindo.has(z.id) ? "… re-extraindo" : "🔄 Só S-5002" }}
        </button>
        <button
          class="btn-danger"
          :disabled="excluindo.has(z.id)"
          @click="disparaExclusao(z)"
          :title="'Excluir zip e eventos indexados'"
        >
          {{ excluindo.has(z.id) ? "… excluindo" : "🗑 Excluir" }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.empty {
  border-radius: 18px;
  padding: 40px 20px;
  text-align: center;
}
.empty-icon {
  font-size: 3rem;
  opacity: 0.6;
}
.empty-title {
  margin-top: 8px;
  color: #fff;
  font-weight: 600;
  font-size: 1.05rem;
}
.empty-sub {
  color: rgba(240, 209, 229, 0.65);
  font-size: 0.9rem;
  margin-top: 4px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.zip-card {
  border-radius: 16px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition:
    transform 160ms ease,
    box-shadow 160ms ease;
}
.zip-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 32px rgba(61, 242, 75, 0.12);
}

.zc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.zc-period {
  font-size: 1.15rem;
  font-weight: 700;
  color: #fff;
  font-variant-numeric: tabular-nums;
}

.badge {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 3px 9px;
  border-radius: 999px;
  border: 1px solid;
  font-weight: 600;
}
.badge.ok {
  color: #3df24b;
  border-color: rgba(61, 242, 75, 0.5);
  background: rgba(61, 242, 75, 0.08);
}
.badge.warn {
  color: #ffd56a;
  border-color: rgba(255, 213, 106, 0.5);
  background: rgba(255, 213, 106, 0.08);
}
.badge.err {
  color: #ff8a8a;
  border-color: rgba(255, 138, 138, 0.5);
  background: rgba(255, 138, 138, 0.08);
}
.badge.neutral {
  color: rgba(240, 209, 229, 0.7);
  border-color: rgba(240, 209, 229, 0.3);
}

.zc-name {
  color: rgba(240, 209, 229, 0.85);
  font-size: 0.85rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  word-break: break-all;
  max-height: 2.4em;
  overflow: hidden;
}

.zc-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 14px;
  margin-top: 4px;
}
.zc-meta > div {
  display: flex;
  flex-direction: column;
}
.lbl {
  font-size: 0.7rem;
  color: rgba(240, 209, 229, 0.55);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.val {
  color: #fff;
  font-weight: 600;
}
.val.accent {
  color: #3df24b;
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-variant-numeric: tabular-nums;
}

.err-msg {
  background: rgba(255, 80, 80, 0.08);
  border: 1px solid rgba(255, 80, 80, 0.3);
  color: #ffb3b3;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 0.85rem;
}

.zc-actions {
  display: flex;
  gap: 8px;
  margin-top: 6px;
  flex-wrap: wrap;
}
.btn-primary {
  flex: 1;
  background: linear-gradient(135deg, #3df24b 0%, #9ff7a6 100%);
  color: #0a1f0c;
  border: none;
  border-radius: 10px;
  padding: 9px 14px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 0 16px rgba(61, 242, 75, 0.32);
  transition:
    transform 120ms ease,
    box-shadow 120ms ease;
  font: inherit;
  font-weight: 700;
}
.btn-primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 0 22px rgba(61, 242, 75, 0.5);
}
.btn-primary:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  box-shadow: none;
}
.btn-ghost {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(240, 209, 229, 0.2);
  color: #fff;
  border-radius: 10px;
  padding: 9px 14px;
  cursor: pointer;
  font: inherit;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
}
.btn-ghost:hover {
  border-color: rgba(240, 209, 229, 0.5);
}
.btn-danger {
  background: transparent;
  color: #ff8a8a;
  border: 1px solid rgba(255, 80, 80, 0.45);
  border-radius: 10px;
  padding: 8px 14px;
  cursor: pointer;
  font: inherit;
}
.btn-danger:hover:not(:disabled) {
  background: rgba(255, 60, 60, 0.12);
  border-color: rgba(255, 90, 90, 0.85);
  color: #ffb3b3;
}
.btn-danger:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
