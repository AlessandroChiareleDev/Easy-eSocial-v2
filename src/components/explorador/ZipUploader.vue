<script setup lang="ts">
import { ref, computed, onUnmounted } from "vue";
import {
  uploadZip,
  detalheZip,
  formatBytes,
  formatRate,
  formatSeconds,
  type UploadProgress,
  type UploadHandle,
  type ZipRow,
} from "@/services/exploradorApi";
import Speedometer from "./Speedometer.vue";

const props = defineProps<{ empresaId: number }>();
const emit = defineEmits<{ (e: "uploaded", zip: ZipRow): void }>();

type Phase = "idle" | "uploading" | "finalizing" | "extraindo" | "ok" | "erro";

const dragOver = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);
const file = ref<File | null>(null);

// período padrão = mês corrente
const today = new Date();
const firstDay = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-01`;
const lastDate = new Date(today.getFullYear(), today.getMonth() + 1, 0);
const lastDay = `${lastDate.getFullYear()}-${String(lastDate.getMonth() + 1).padStart(2, "0")}-${String(lastDate.getDate()).padStart(2, "0")}`;

const dtIni = ref(firstDay);
const dtFim = ref(lastDay);

const phase = ref<Phase>("idle");
const progress = ref<UploadProgress | null>(null);
const errorMsg = ref<string | null>(null);
const handle = ref<UploadHandle | null>(null);

// Pico observado para mostrar "máx" (curiosidade visual)
const peakRate = ref(0);

let pollTimer: number | null = null;

const acceptZip = ".zip,application/zip,application/x-zip-compressed";

function pickFile() {
  fileInput.value?.click();
}

function onFileChange(e: Event) {
  const t = e.target as HTMLInputElement;
  if (t.files && t.files[0]) selectFile(t.files[0]);
  t.value = "";
}

function onDrop(e: DragEvent) {
  e.preventDefault();
  dragOver.value = false;
  const f = e.dataTransfer?.files?.[0];
  if (f) selectFile(f);
}

function selectFile(f: File) {
  if (!f.name.toLowerCase().endsWith(".zip")) {
    errorMsg.value = "Só aceita arquivo .zip";
    return;
  }
  errorMsg.value = null;
  file.value = f;
  // Tenta inferir período pelo nome (ex: SOLUCOES_2025-08.zip)
  const m = f.name.match(/(\d{4})[-_](\d{2})/);
  if (m) {
    const y = m[1];
    const mo = m[2];
    const last = new Date(Number(y), Number(mo), 0);
    dtIni.value = `${y}-${mo}-01`;
    dtFim.value = `${y}-${mo}-${String(last.getDate()).padStart(2, "0")}`;
  }
}

async function startUpload() {
  if (!file.value) return;
  phase.value = "uploading";
  progress.value = null;
  peakRate.value = 0;
  errorMsg.value = null;

  const h = uploadZip({
    file: file.value,
    empresaId: props.empresaId,
    dtIni: dtIni.value,
    dtFim: dtFim.value,
    onProgress: (p) => {
      progress.value = p;
      if (p.rate > peakRate.value) peakRate.value = p.rate;
    },
    onUploadFinished: () => {
      phase.value = "finalizing";
    },
  });
  handle.value = h;

  try {
    const res = await h.promise;
    handle.value = null;

    if (res.duplicado) {
      // já existia — só busca o zip e emite
      const det = await detalheZip(res.zip_id);
      phase.value = "ok";
      emit("uploaded", det.zip);
      return;
    }

    // upload OK → backend ainda não extraiu (chama /extrair)
    phase.value = "extraindo";
    await pollExtracao(res.zip_id);
  } catch (e) {
    handle.value = null;
    if ((e as DOMException)?.name === "AbortError") {
      phase.value = "idle";
      return;
    }
    phase.value = "erro";
    errorMsg.value = (e as Error).message || "falha no upload";
  }
}

async function pollExtracao(zipId: number) {
  // Dispara extração e aguarda concluir
  try {
    const r = await fetch(
      `/explorador-api/api/explorador/zips/${zipId}/extrair`,
      {
        method: "POST",
      },
    );
    if (!r.ok) throw new Error(`extração: HTTP ${r.status}`);
    // Quando o POST volta, já está extraído (síncrono)
    const det = await detalheZip(zipId);
    phase.value = "ok";
    emit("uploaded", det.zip);
  } catch (e) {
    phase.value = "erro";
    errorMsg.value = (e as Error).message;
  }
}

function cancel() {
  handle.value?.abort();
  handle.value = null;
  phase.value = "idle";
  progress.value = null;
}

function reset() {
  file.value = null;
  phase.value = "idle";
  progress.value = null;
  errorMsg.value = null;
}

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer);
  handle.value?.abort();
});

const percent = computed(() => progress.value?.percent ?? 0);
const rateLabel = computed(() =>
  progress.value ? formatRate(progress.value.rate) : "—",
);
const peakLabel = computed(() =>
  peakRate.value > 0 ? formatRate(peakRate.value) : "—",
);
const etaLabel = computed(() =>
  progress.value ? formatSeconds(progress.value.eta) : "—",
);
const sentLabel = computed(() =>
  progress.value
    ? `${formatBytes(progress.value.loaded)} / ${formatBytes(progress.value.total)}`
    : "",
);
</script>

<template>
  <div class="uploader liquid-glass">
    <!-- ESTADO 1: idle / arquivo selecionado -->
    <template v-if="phase === 'idle' || phase === 'erro'">
      <div
        class="dropzone"
        :class="{ over: dragOver, hasFile: !!file }"
        @dragover.prevent="dragOver = true"
        @dragleave="dragOver = false"
        @drop="onDrop"
        @click="pickFile"
      >
        <input
          ref="fileInput"
          type="file"
          :accept="acceptZip"
          class="file-input"
          @change="onFileChange"
        />

        <div v-if="!file" class="dz-empty">
          <div class="dz-icon">⬆</div>
          <div class="dz-title gg-glow">
            Arraste um arquivo .zip do eSocial aqui
          </div>
          <div class="dz-sub">
            ou <span class="link">clique para selecionar</span>
          </div>
        </div>

        <div v-else class="dz-file">
          <div class="dz-icon ok">📦</div>
          <div class="dz-file-info">
            <div class="dz-file-name">{{ file.name }}</div>
            <div class="dz-file-meta">{{ formatBytes(file.size) }}</div>
          </div>
          <button class="btn-ghost" @click.stop="reset">trocar</button>
        </div>
      </div>

      <div v-if="file" class="period-row">
        <label>
          <span>Início</span>
          <input v-model="dtIni" type="date" />
        </label>
        <label>
          <span>Fim</span>
          <input v-model="dtFim" type="date" />
        </label>
      </div>

      <div v-if="errorMsg" class="error">⚠ {{ errorMsg }}</div>

      <div v-if="file" class="actions">
        <button class="btn-primary" @click="startUpload">
          ▶ Iniciar upload
        </button>
      </div>
    </template>

    <!-- ESTADO 2: upload em andamento -->
    <template v-else-if="phase === 'uploading'">
      <div class="uploading-stage">
        <Speedometer
          :percent="percent"
          :label="`${percent.toFixed(1)}%`"
          :sublabel="rateLabel"
          :size="260"
        />
        <div class="up-stats">
          <div class="up-row">
            <div class="lbl">Arquivo</div>
            <div class="val mono">{{ file?.name }}</div>
          </div>
          <div class="up-row">
            <div class="lbl">Enviado</div>
            <div class="val mono">{{ sentLabel }}</div>
          </div>
          <div class="up-row">
            <div class="lbl">Velocidade</div>
            <div class="val mono accent">{{ rateLabel }}</div>
          </div>
          <div class="up-row">
            <div class="lbl">Pico</div>
            <div class="val mono">{{ peakLabel }}</div>
          </div>
          <div class="up-row">
            <div class="lbl">ETA</div>
            <div class="val mono">{{ etaLabel }}</div>
          </div>
          <div class="up-actions">
            <button class="btn-ghost danger" @click="cancel">cancelar</button>
          </div>
        </div>
      </div>
    </template>

    <!-- ESTADO 2.5: finalizando upload (servidor processando) -->
    <template v-else-if="phase === 'finalizing'">
      <div class="extract-stage">
        <div class="spinner"></div>
        <div class="ex-title gg-glow">Finalizando upload no servidor…</div>
        <div class="ex-sub">
          Bytes recebidos. Calculando SHA-256 e gravando no banco — isso pode
          levar até 1 minuto para arquivos grandes.
        </div>
      </div>
    </template>

    <!-- ESTADO 3: extraindo -->
    <template v-else-if="phase === 'extraindo'">
      <div class="extract-stage">
        <div class="spinner"></div>
        <div class="ex-title gg-glow">Extraindo XMLs do zip…</div>
        <div class="ex-sub">
          Indexando eventos eSocial — isso pode levar alguns minutos.
        </div>
      </div>
    </template>

    <!-- ESTADO 4: ok -->
    <template v-else-if="phase === 'ok'">
      <div class="done-stage">
        <div class="done-icon">✓</div>
        <div class="done-title gg-glow">Upload concluído</div>
        <div class="done-sub">
          O zip foi indexado e está pronto para visualizar.
        </div>
        <button class="btn-primary" @click="reset">+ Subir outro</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.uploader {
  border-radius: 18px;
  padding: 22px;
}

/* Drop zone */
.dropzone {
  position: relative;
  border: 2px dashed rgba(61, 242, 75, 0.35);
  border-radius: 14px;
  padding: 36px 24px;
  text-align: center;
  transition: all 200ms ease;
  cursor: pointer;
  background: rgba(61, 242, 75, 0.03);
}
.dropzone:hover,
.dropzone.over {
  border-color: rgba(61, 242, 75, 0.85);
  background: rgba(61, 242, 75, 0.07);
  box-shadow:
    inset 0 0 30px rgba(61, 242, 75, 0.08),
    0 0 24px rgba(61, 242, 75, 0.18);
}
.dropzone.hasFile {
  border-style: solid;
  border-color: rgba(240, 209, 229, 0.4);
  background: rgba(240, 209, 229, 0.04);
}
.file-input {
  display: none;
}
.dz-empty .dz-icon {
  font-size: 3rem;
  line-height: 1;
  margin-bottom: 10px;
  color: #3df24b;
  text-shadow: 0 0 16px rgba(61, 242, 75, 0.65);
}
.dz-title {
  font-size: 1.1rem;
  font-weight: 600;
  color: #fff;
  margin-bottom: 4px;
}
.dz-sub {
  color: rgba(240, 209, 229, 0.7);
  font-size: 0.9rem;
}
.link {
  color: #3df24b;
  text-decoration: underline;
}

.dz-file {
  display: flex;
  align-items: center;
  gap: 14px;
  text-align: left;
}
.dz-file .dz-icon {
  font-size: 2rem;
}
.dz-file-info {
  flex: 1;
}
.dz-file-name {
  color: #fff;
  font-weight: 600;
  word-break: break-all;
}
.dz-file-meta {
  color: rgba(240, 209, 229, 0.65);
  font-size: 0.85rem;
  margin-top: 2px;
}

/* Período */
.period-row {
  display: flex;
  gap: 14px;
  margin-top: 16px;
}
.period-row label {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 0.85rem;
  color: rgba(240, 209, 229, 0.75);
}
.period-row input {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(240, 209, 229, 0.18);
  border-radius: 8px;
  padding: 8px 10px;
  color: #fff;
  font: inherit;
  color-scheme: dark;
}
.period-row input:focus {
  outline: none;
  border-color: rgba(61, 242, 75, 0.6);
}

.error {
  margin-top: 12px;
  background: rgba(255, 80, 80, 0.1);
  border: 1px solid rgba(255, 80, 80, 0.35);
  color: #ffb3b3;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 0.9rem;
}

.actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.btn-primary {
  background: linear-gradient(135deg, #3df24b 0%, #9ff7a6 100%);
  color: #0a1f0c;
  border: none;
  border-radius: 10px;
  padding: 10px 20px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 0 18px rgba(61, 242, 75, 0.4);
  transition:
    transform 120ms ease,
    box-shadow 120ms ease;
}
.btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 0 26px rgba(61, 242, 75, 0.6);
}
.btn-ghost {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(240, 209, 229, 0.2);
  color: #fff;
  border-radius: 8px;
  padding: 7px 14px;
  cursor: pointer;
  font: inherit;
}
.btn-ghost:hover {
  border-color: rgba(240, 209, 229, 0.5);
}
.btn-ghost.danger {
  border-color: rgba(255, 120, 120, 0.4);
  color: #ffb3b3;
}

/* Uploading */
.uploading-stage {
  display: flex;
  align-items: center;
  gap: 28px;
  flex-wrap: wrap;
  justify-content: center;
}
.up-stats {
  flex: 1;
  min-width: 260px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.up-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(240, 209, 229, 0.08);
}
.lbl {
  color: rgba(240, 209, 229, 0.65);
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.val {
  color: #fff;
  font-weight: 600;
}
.val.accent {
  color: #3df24b;
  text-shadow: 0 0 8px rgba(61, 242, 75, 0.4);
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-variant-numeric: tabular-nums;
}
.up-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}

/* Extraindo */
.extract-stage {
  text-align: center;
  padding: 30px 10px;
}
.spinner {
  width: 56px;
  height: 56px;
  border: 4px solid rgba(61, 242, 75, 0.15);
  border-top-color: #3df24b;
  border-radius: 50%;
  margin: 0 auto 18px;
  animation: spin 900ms linear infinite;
  box-shadow: 0 0 24px rgba(61, 242, 75, 0.35);
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.ex-title {
  font-size: 1.2rem;
  color: #fff;
  font-weight: 600;
  margin-bottom: 6px;
}
.ex-sub {
  color: rgba(240, 209, 229, 0.7);
  font-size: 0.9rem;
}

/* Done */
.done-stage {
  text-align: center;
  padding: 22px 10px;
}
.done-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3df24b, #9ff7a6);
  color: #0a1f0c;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2.2rem;
  font-weight: 800;
  margin: 0 auto 14px;
  box-shadow: 0 0 28px rgba(61, 242, 75, 0.55);
}
.done-title {
  font-size: 1.2rem;
  font-weight: 700;
  color: #fff;
}
.done-sub {
  color: rgba(240, 209, 229, 0.7);
  margin: 6px 0 18px;
  font-size: 0.9rem;
}
</style>
