<script setup lang="ts">
import { ref, computed, onUnmounted } from "vue";
import {
  uploadZip,
  detalheZip,
  extrairZip,
  progressoExtracao,
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

// MULTI-ARQUIVO: lista de arquivos selecionados (todos vao para o mesmo periodo)
const files = ref<File[]>([]);
// Indice do arquivo atualmente em upload (0-based). Total = files.value.length
const currentIdx = ref(0);
// Resultado por arquivo (para mostrar resumo no fim)
interface FileResult {
  nome: string;
  ok: boolean;
  zip_id?: number;
  erro?: string;
  duplicado?: boolean;
  // estatisticas vindas do /extrair
  total_xmls?: number;
  indexados?: number;
  duplicados_id_evento?: number;
}
const resultados = ref<FileResult[]>([]);

// --- Terminal de logs (timeline visual de cada passo) ---
type LogLevel = "info" | "ok" | "warn" | "err" | "step";
interface LogLine {
  t: string; // HH:MM:SS
  arquivo?: string;
  nivel: LogLevel;
  msg: string;
}
const logs = ref<LogLine[]>([]);
const termRef = ref<HTMLElement | null>(null);
function hora() {
  const d = new Date();
  return (
    String(d.getHours()).padStart(2, "0") +
    ":" +
    String(d.getMinutes()).padStart(2, "0") +
    ":" +
    String(d.getSeconds()).padStart(2, "0")
  );
}
function log(nivel: LogLevel, msg: string, arquivo?: string) {
  const line: LogLine = { t: hora(), nivel, msg };
  if (arquivo !== undefined) line.arquivo = arquivo;
  logs.value.push(line);
  // auto-scroll
  requestAnimationFrame(() => {
    if (termRef.value) termRef.value.scrollTop = termRef.value.scrollHeight;
  });
}
function humanizeErro(raw: string): string {
  // Pega payloads {"detail":"..."} e tenta dar contexto util
  try {
    const m = raw.match(/\{[\s\S]*\}/);
    if (m) {
      const j = JSON.parse(m[0]);
      if (j.detail) return String(j.detail);
    }
  } catch {
    // ignore
  }
  if (/Failed to fetch|NetworkError/i.test(raw))
    return "rede caiu / backend offline";
  if (/401/.test(raw)) return "sessão expirou — refaça o login";
  if (/403/.test(raw)) return "sem permissão pra essa empresa";
  if (/404/.test(raw)) return "zip não encontrado no banco (após upload)";
  if (/413/.test(raw)) return "arquivo grande demais";
  if (/timeout/i.test(raw)) return "timeout — servidor demorou demais";
  return raw;
}

// Compat: alguns trechos do template ainda referenciam "file"
const file = computed<File | null>(
  () => files.value[currentIdx.value] ?? files.value[0] ?? null,
);
const total = computed(() => files.value.length);
const progressoLote = computed(() =>
  total.value > 1 ? `Arquivo ${currentIdx.value + 1} de ${total.value}` : "",
);

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

// Progresso da extração (polling no endpoint /progresso)
interface ExtracaoProg {
  processados: number;
  total: number;
  percent: number;
  ok: number;
  duplicados: number;
  falhas: number;
  etapa: string;
}
const extracaoProg = ref<ExtracaoProg>({
  processados: 0,
  total: 0,
  percent: 0,
  ok: 0,
  duplicados: 0,
  falhas: 0,
  etapa: "",
});
function resetExtracaoProg() {
  extracaoProg.value = {
    processados: 0,
    total: 0,
    percent: 0,
    ok: 0,
    duplicados: 0,
    falhas: 0,
    etapa: "",
  };
}

let pollTimer: number | null = null;
// Flag para cancelar o loop sequencial
let cancelLoop = false;

const acceptZip = ".zip,application/zip,application/x-zip-compressed";

function pickFile() {
  fileInput.value?.click();
}

function onFileChange(e: Event) {
  const t = e.target as HTMLInputElement;
  if (t.files && t.files.length > 0) selectFiles(t.files);
  t.value = "";
}

function onDrop(e: DragEvent) {
  e.preventDefault();
  dragOver.value = false;
  const fs = e.dataTransfer?.files;
  if (fs && fs.length > 0) selectFiles(fs);
}

function selectFiles(fs: FileList) {
  const arr = Array.from(fs);
  const naoZip = arr.filter((f) => !f.name.toLowerCase().endsWith(".zip"));
  if (naoZip.length > 0) {
    errorMsg.value =
      `Só aceita arquivos .zip. Inválidos: ` +
      naoZip.map((f) => f.name).join(", ");
    return;
  }
  errorMsg.value = null;
  // ACUMULA: nao sobrescreve. Se ja tinha arquivos, adiciona os novos
  // ignorando duplicados (mesmo nome + tamanho).
  const existentes = new Set(files.value.map((f) => `${f.name}:${f.size}`));
  const novos = arr.filter((f) => !existentes.has(`${f.name}:${f.size}`));
  const ignorados = arr.length - novos.length;
  files.value = [...files.value, ...novos];
  if (ignorados > 0) {
    errorMsg.value = `${ignorados} arquivo(s) ignorado(s) (já estavam na lista).`;
  }
  currentIdx.value = 0;
  // Tenta inferir período pelo nome do primeiro arquivo (ex: SOLUCOES_2025-08.zip)
  const primeiro = files.value[0];
  const m = primeiro ? primeiro.name.match(/(\d{4})[-_](\d{2})/) : null;
  if (m) {
    const y = m[1];
    const mo = m[2];
    const last = new Date(Number(y), Number(mo), 0);
    dtIni.value = `${y}-${mo}-01`;
    dtFim.value = `${y}-${mo}-${String(last.getDate()).padStart(2, "0")}`;
  }
}

function removerArquivo(idx: number) {
  files.value = files.value.filter((_, i) => i !== idx);
  if (currentIdx.value >= files.value.length) currentIdx.value = 0;
}

async function uploadUm(f: File): Promise<void> {
  phase.value = "uploading";
  progress.value = null;
  peakRate.value = 0;

  // Captura o empresaId no momento do upload e usa o MESMO valor no extrair.
  // Evita race se o usuario trocar de empresa enquanto sobe.
  const empresaIdSnapshot = props.empresaId;
  log(
    "step",
    `▶ início (empresa_id=${empresaIdSnapshot}, ${formatBytes(f.size)}, período ${dtIni.value}→${dtFim.value})`,
    f.name,
  );

  const h = uploadZip({
    file: f,
    empresaId: empresaIdSnapshot,
    dtIni: dtIni.value,
    dtFim: dtFim.value,
    onProgress: (p) => {
      progress.value = p;
      if (p.rate > peakRate.value) peakRate.value = p.rate;
    },
    onUploadFinished: () => {
      phase.value = "finalizing";
      log("info", "bytes recebidos — calculando SHA-256 + gravando", f.name);
    },
  });
  handle.value = h;

  try {
    const res = await h.promise;
    handle.value = null;

    if (res.duplicado) {
      log(
        "warn",
        `zip já existia (zip_id=${res.zip_id}) — nada gravado`,
        f.name,
      );
      const det = await detalheZip(res.zip_id);
      emit("uploaded", det.zip);
      resultados.value.push({
        nome: f.name,
        ok: true,
        zip_id: res.zip_id,
        duplicado: true,
      });
      return;
    }

    log("ok", `upload ok → zip_id=${res.zip_id}, iniciando extração`, f.name);
    phase.value = "extraindo";
    resetExtracaoProg();

    // Dispara extracao em background (endpoint retorna 202 imediatamente).
    await extrairZip(res.zip_id, { empresaId: empresaIdSnapshot });

    // Faz polling do progresso ate status final (ok / erro).
    let lastPctLogado = -1;
    const extractStats = await new Promise<{
      total_xmls: number;
      indexados: number;
      duplicados_id_evento: number;
      falhas: number;
    }>((resolve, reject) => {
      const pollId = window.setInterval(async () => {
        try {
          const p = await progressoExtracao(res.zip_id, {
            empresaId: empresaIdSnapshot,
          });
          extracaoProg.value = {
            processados: p.processados,
            total: p.total,
            percent: p.percent,
            ok: p.ok,
            duplicados: p.duplicados,
            falhas: p.falhas,
            etapa: p.etapa ?? "",
          };
          const marco = Math.floor(p.percent / 10) * 10;
          if (marco > lastPctLogado && p.total > 0) {
            lastPctLogado = marco;
            log(
              "info",
              `⚙ ${p.processados}/${p.total} (${p.percent}%)`,
              f.name,
            );
          }
          if (p.status === "ok") {
            window.clearInterval(pollId);
            resolve({
              total_xmls: p.total || p.processados,
              indexados: p.ok,
              duplicados_id_evento: p.duplicados,
              falhas: p.falhas,
            });
          } else if (p.status === "erro") {
            window.clearInterval(pollId);
            reject(new Error(p.erro || "extracao falhou"));
          }
        } catch {
          // ignora erro pontual de polling — tenta de novo no proximo tick
        }
      }, 1500);
    });
    log(
      "ok",
      `extração ok: ${extractStats.indexados}/${extractStats.total_xmls} XMLs indexados` +
        (extractStats.duplicados_id_evento
          ? ` (♻ ${extractStats.duplicados_id_evento} dup ignorados)`
          : ""),
      f.name,
    );
    const det = await detalheZip(res.zip_id);
    emit("uploaded", det.zip);
    resultados.value.push({
      nome: f.name,
      ok: true,
      zip_id: res.zip_id,
      total_xmls: extractStats.total_xmls,
      indexados: extractStats.indexados,
      duplicados_id_evento: extractStats.duplicados_id_evento,
    });
  } catch (e) {
    handle.value = null;
    if ((e as DOMException)?.name === "AbortError") {
      log("warn", "cancelado", f.name);
      resultados.value.push({ nome: f.name, ok: false, erro: "cancelado" });
      throw e;
    }
    const raw = (e as Error).message || "falha";
    const erro = humanizeErro(raw);
    log("err", erro, f.name);
    resultados.value.push({
      nome: f.name,
      ok: false,
      erro,
    });
    // NAO relanca: queremos continuar pros proximos arquivos
  }
}

async function startUpload() {
  if (files.value.length === 0) return;
  errorMsg.value = null;
  resultados.value = [];
  logs.value = [];
  cancelLoop = false;
  log("step", `═ Lote iniciado: ${files.value.length} arquivo(s) ═`);

  for (let i = 0; i < files.value.length; i++) {
    if (cancelLoop) break;
    const f = files.value[i];
    if (!f) continue;
    currentIdx.value = i;
    log("step", `─── [${i + 1}/${files.value.length}] ${f.name} ───`);
    try {
      await uploadUm(f);
    } catch (e) {
      if ((e as DOMException)?.name === "AbortError") {
        // cancelado pelo usuario: para o loop
        phase.value = "idle";
        return;
      }
      // outros erros: ja foram registrados em resultados, segue pro proximo
    }
  }

  // Resumo final
  const okN = resultados.value.filter((r) => r.ok).length;
  const falhaN = resultados.value.filter((r) => !r.ok).length;
  log(
    falhaN === 0 ? "ok" : okN === 0 ? "err" : "warn",
    `═ Fim do lote: ${okN} ok / ${falhaN} falha(s) ═`,
  );
  if (falhaN === 0) {
    phase.value = "ok";
  } else if (okN === 0) {
    phase.value = "erro";
    errorMsg.value =
      `Todos os ${falhaN} arquivos falharam:\n` +
      resultados.value.map((r) => `• ${r.nome}: ${r.erro}`).join("\n");
  } else {
    phase.value = "ok";
  }
}

function cancel() {
  cancelLoop = true;
  handle.value?.abort();
  handle.value = null;
  phase.value = "idle";
  progress.value = null;
}

function reset() {
  files.value = [];
  currentIdx.value = 0;
  resultados.value = [];
  logs.value = [];
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
const totalBytesSelecionados = computed(() =>
  files.value.reduce((acc, f) => acc + f.size, 0),
);

// Totais agregados de todos os arquivos processados (para mostrar no fim)
const totaisAgregados = computed(() => {
  let totalXmls = 0;
  let indexados = 0;
  let duplicados = 0;
  for (const r of resultados.value) {
    if (!r.ok) continue;
    totalXmls += r.total_xmls ?? 0;
    indexados += r.indexados ?? 0;
    duplicados += r.duplicados_id_evento ?? 0;
  }
  return { totalXmls, indexados, duplicados };
});
</script>

<template>
  <div class="uploader liquid-glass">
    <!-- ESTADO 1: idle / arquivos selecionados -->
    <template v-if="phase === 'idle' || phase === 'erro'">
      <div
        class="dropzone"
        :class="{ over: dragOver, hasFile: files.length > 0 }"
        @dragover.prevent="dragOver = true"
        @dragleave="dragOver = false"
        @drop="onDrop"
        @click="pickFile"
      >
        <input
          ref="fileInput"
          type="file"
          :accept="acceptZip"
          multiple
          class="file-input"
          @change="onFileChange"
        />

        <div v-if="files.length === 0" class="dz-empty">
          <div class="dz-icon">⬆</div>
          <div class="dz-title gg-glow">
            Arraste um ou mais .zip do eSocial aqui
          </div>
          <div class="dz-sub">
            ou <span class="link">clique para selecionar</span>
            <br />
            <small
              >Pode subir vários ZIPs do mesmo mês — todos vão para o mesmo
              período. Chain walk consolidado automático.</small
            >
          </div>
        </div>

        <div v-else class="dz-files-list" @click.stop>
          <div class="dz-files-head">
            <div class="dz-icon ok">📦</div>
            <div class="dz-files-title">
              {{ files.length }} arquivo{{
                files.length === 1 ? "" : "s"
              }}
              selecionado{{ files.length === 1 ? "" : "s" }}
              <span class="dz-files-bytes mono"
                >· {{ formatBytes(totalBytesSelecionados) }}</span
              >
            </div>
            <button class="btn-primary btn-sm" @click.stop="pickFile">
              + Adicionar mais
            </button>
            <button class="btn-ghost btn-sm" @click.stop="reset">limpar</button>
          </div>
          <ul class="dz-files-ul">
            <li
              v-for="(f, i) in files"
              :key="`${f.name}-${f.size}-${i}`"
              class="dz-file-row"
            >
              <span class="dz-file-name">{{ f.name }}</span>
              <span class="dz-file-meta mono">{{ formatBytes(f.size) }}</span>
              <button
                class="btn-ghost btn-xs"
                @click.stop="removerArquivo(i)"
                title="Remover este arquivo da lista"
              >
                ✕
              </button>
            </li>
          </ul>
          <div class="dz-hint">
            💡 Pode clicar em <strong>+ Adicionar mais</strong>, arrastar outros
            ZIPs aqui, ou segurar <kbd>Ctrl</kbd> ao selecionar pra pegar vários
            de uma vez.
          </div>
        </div>
      </div>

      <div v-if="files.length > 0" class="period-row">
        <label>
          <span>Início</span>
          <input v-model="dtIni" type="date" />
        </label>
        <label>
          <span>Fim</span>
          <input v-model="dtFim" type="date" />
        </label>
      </div>

      <div v-if="files.length > 0" class="period-hint">
        ℹ Todos os {{ files.length }} arquivos vão para o mesmo período
        <strong>{{ dtIni }} → {{ dtFim }}</strong
        >. Os ZIPs aparecem agrupados em 1 card de mês na listagem.
      </div>

      <div v-if="errorMsg" class="error">⚠ {{ errorMsg }}</div>

      <div v-if="files.length > 0" class="actions">
        <button class="btn-primary" @click="startUpload">
          ▶ Iniciar upload
          <span v-if="files.length > 1">({{ files.length }} arquivos)</span>
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
          <div v-if="progressoLote" class="up-row hot">
            <div class="lbl">Lote</div>
            <div class="val mono accent">{{ progressoLote }}</div>
          </div>
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
            <button class="btn-ghost danger" @click="cancel">
              cancelar lote
            </button>
          </div>
        </div>
      </div>
    </template>

    <!-- ESTADO 2.5: finalizando upload (servidor processando) -->
    <template v-else-if="phase === 'finalizing'">
      <div class="extract-stage">
        <div class="spinner"></div>
        <div v-if="progressoLote" class="ex-lote">{{ progressoLote }}</div>
        <div class="ex-title gg-glow">Finalizando upload no servidor…</div>
        <div class="ex-sub">
          <strong>{{ file?.name }}</strong> — Bytes recebidos. Calculando
          SHA-256 e gravando no banco.
        </div>
      </div>
    </template>

    <!-- ESTADO 3: extraindo -->
    <template v-else-if="phase === 'extraindo'">
      <div class="extract-stage">
        <div class="spinner"></div>
        <div v-if="progressoLote" class="ex-lote">{{ progressoLote }}</div>
        <div class="ex-title gg-glow">Extraindo XMLs do zip…</div>
        <div class="ex-sub">
          <strong>{{ file?.name }}</strong> — Indexando eventos eSocial.
        </div>
        <div
          class="ex-progress"
          v-if="extracaoProg.total > 0 || extracaoProg.processados > 0"
        >
          <div class="ex-bar">
            <div
              class="ex-bar-fill"
              :style="{ width: extracaoProg.percent + '%' }"
            ></div>
          </div>
          <div class="ex-counter mono">
            {{ extracaoProg.processados }} /
            {{ extracaoProg.total || "?" }} XMLs
            <span v-if="extracaoProg.total">· {{ extracaoProg.percent }}%</span>
            <span v-if="extracaoProg.ok"> · {{ extracaoProg.ok }} novos</span>
            <span v-if="extracaoProg.duplicados">
              · {{ extracaoProg.duplicados }} dup</span
            >
            <span v-if="extracaoProg.falhas">
              · {{ extracaoProg.falhas }} falhas</span
            >
          </div>
        </div>
      </div>
    </template>

    <!-- ESTADO 4: ok (todos ou parcialmente concluido) -->
    <template v-else-if="phase === 'ok'">
      <div class="done-stage">
        <div class="done-icon">✓</div>
        <div class="done-title gg-glow">
          {{
            resultados.filter((r) => !r.ok).length > 0
              ? "Upload parcial"
              : "Upload concluído"
          }}
        </div>
        <div class="done-sub">
          {{ resultados.filter((r) => r.ok).length }} de
          {{ resultados.length }} arquivo(s) processado(s) com sucesso.
        </div>

        <!-- Resumo agregado de duplicados detectados e resolvidos -->
        <div v-if="totaisAgregados.totalXmls > 0" class="dedup-resumo">
          <div class="dedup-line">
            📦
            <strong>{{ totaisAgregados.totalXmls.toLocaleString() }}</strong>
            XMLs lidos · ✅
            <strong class="ok">{{
              totaisAgregados.indexados.toLocaleString()
            }}</strong>
            indexados
            <span v-if="totaisAgregados.duplicados > 0">
              · ♻
              <strong class="warn">{{
                totaisAgregados.duplicados.toLocaleString()
              }}</strong>
              duplicados detectados
            </span>
          </div>
          <div v-if="totaisAgregados.duplicados > 0" class="dedup-info">
            ℹ Os <strong>{{ totaisAgregados.duplicados }}</strong> XMLs
            duplicados (mesmo evento eSocial presente em mais de um ZIP) foram
            <strong>detectados automaticamente e ignorados</strong> — o banco
            tem 1 linha única por evento. Nenhum dado foi duplicado.
          </div>
        </div>

        <ul v-if="resultados.length >= 1" class="resultados-ul">
          <li
            v-for="(r, i) in resultados"
            :key="i"
            :class="{ ok: r.ok, err: !r.ok }"
          >
            <span class="r-icon">{{ r.ok ? "✓" : "✕" }}</span>
            <span class="r-nome mono">{{ r.nome }}</span>
            <span v-if="r.duplicado" class="r-tag">já existia</span>
            <span
              v-else-if="r.ok && (r.duplicados_id_evento ?? 0) > 0"
              class="r-tag warn"
              :title="`${r.indexados} novos / ${r.duplicados_id_evento} já estavam de outro ZIP`"
            >
              ♻ {{ r.duplicados_id_evento }} dup
            </span>
            <span
              v-else-if="r.ok && r.indexados !== undefined"
              class="r-tag ok"
            >
              {{ r.indexados }} XMLs
            </span>
            <span v-if="!r.ok" class="r-erro">{{ r.erro }}</span>
          </li>
        </ul>
        <button class="btn-primary" @click="reset">+ Subir outro(s)</button>
      </div>
    </template>

    <!-- TERMINAL DE LOGS (sempre visivel quando ha qualquer log) -->
    <div v-if="logs.length > 0" class="term-panel">
      <div class="term-head">
        <span class="term-dot r"></span>
        <span class="term-dot y"></span>
        <span class="term-dot g"></span>
        <span class="term-title mono">upload.log</span>
        <button
          class="btn-ghost btn-xs term-clear"
          @click="logs = []"
          title="Limpar log"
        >
          limpar
        </button>
      </div>
      <pre ref="termRef" class="term-body mono">
<span
            v-for="(l, i) in logs"
            :key="i"
            :class="['term-line', `lvl-${l.nivel}`]"
          ><span class="term-t">[{{ l.t }}]</span><span
              v-if="l.arquivo"
              class="term-arq"
            > {{ l.arquivo }}</span><span class="term-msg"> {{ l.msg }}</span>
</span></pre>
    </div>
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
.ex-progress {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: center;
}
.ex-bar {
  width: min(420px, 80%);
  height: 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(240, 209, 229, 0.1);
  overflow: hidden;
}
.ex-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #c44a8a, #f5b3d8);
  box-shadow: 0 0 12px rgba(196, 74, 138, 0.5);
  transition: width 0.4s ease;
}
.ex-counter {
  color: rgba(240, 209, 229, 0.85);
  font-size: 0.85rem;
  letter-spacing: 0.02em;
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

/* Lista de arquivos selecionados (multi-upload) */
.dz-files-list {
  text-align: left;
}
.dz-files-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.dz-files-head .dz-icon {
  font-size: 1.8rem;
}
.dz-files-title {
  flex: 1;
  color: #fff;
  font-weight: 600;
}
.dz-files-bytes {
  color: rgba(240, 209, 229, 0.65);
  font-weight: 400;
  font-size: 0.85rem;
  margin-left: 6px;
}
.dz-files-ul {
  list-style: none;
  padding: 0;
  margin: 0;
  max-height: 220px;
  overflow-y: auto;
  border-top: 1px solid rgba(240, 209, 229, 0.1);
}
.dz-file-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 4px;
  border-bottom: 1px solid rgba(240, 209, 229, 0.06);
  font-size: 0.85rem;
}
.dz-file-row .dz-file-name {
  flex: 1;
  color: #fff;
  word-break: break-all;
}
.dz-file-row .dz-file-meta {
  color: rgba(240, 209, 229, 0.6);
  font-size: 0.78rem;
}
.btn-xs {
  padding: 2px 8px;
  font-size: 0.75rem;
}
.btn-sm {
  padding: 4px 12px;
  font-size: 0.8rem;
}

.dz-hint {
  margin-top: 10px;
  padding: 8px 12px;
  font-size: 0.8rem;
  color: rgba(240, 209, 229, 0.7);
  background: rgba(61, 242, 75, 0.04);
  border-left: 3px solid rgba(61, 242, 75, 0.45);
  border-radius: 4px;
}
.dz-hint strong {
  color: #3df24b;
}
.dz-hint kbd {
  display: inline-block;
  padding: 1px 6px;
  font-family: ui-monospace, monospace;
  font-size: 0.75rem;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 3px;
  color: #fff;
}

.period-hint {
  margin-top: 10px;
  padding: 8px 12px;
  background: rgba(61, 242, 75, 0.05);
  border: 1px solid rgba(61, 242, 75, 0.18);
  border-radius: 8px;
  font-size: 0.85rem;
  color: rgba(240, 209, 229, 0.85);
}
.period-hint strong {
  color: #3df24b;
}

.up-row.hot .val {
  color: #3df24b;
  font-weight: 700;
}

.ex-lote {
  display: inline-block;
  margin-bottom: 8px;
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(61, 242, 75, 0.12);
  border: 1px solid rgba(61, 242, 75, 0.35);
  color: #3df24b;
  font-size: 0.8rem;
  font-weight: 700;
}

.resultados-ul {
  list-style: none;
  padding: 0;
  margin: 14px 0 18px;
  text-align: left;
  max-height: 200px;
  overflow-y: auto;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
}
.resultados-ul li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  font-size: 0.85rem;
  border-bottom: 1px solid rgba(240, 209, 229, 0.06);
}
.resultados-ul li.ok .r-icon {
  color: #3df24b;
}
.resultados-ul li.err .r-icon {
  color: #f55;
}
.resultados-ul .r-nome {
  flex: 1;
  word-break: break-all;
}
.resultados-ul .r-tag {
  font-size: 0.7rem;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(240, 209, 229, 0.15);
  color: rgba(240, 209, 229, 0.8);
}
.resultados-ul .r-erro {
  font-size: 0.75rem;
  color: #f88;
}

/* Resumo de dedup no estado final */
.dedup-resumo {
  margin: 14px 0;
  padding: 12px 14px;
  background: rgba(61, 242, 75, 0.04);
  border: 1px solid rgba(61, 242, 75, 0.22);
  border-radius: 10px;
  text-align: left;
}
.dedup-line {
  font-size: 0.95rem;
  color: rgba(240, 209, 229, 0.9);
}
.dedup-line .ok {
  color: #3df24b;
}
.dedup-line .warn {
  color: #ffd56a;
}
.dedup-info {
  margin-top: 8px;
  font-size: 0.82rem;
  color: rgba(240, 209, 229, 0.75);
  line-height: 1.4;
}
.dedup-info strong {
  color: #ffd56a;
}

.resultados-ul .r-tag.warn {
  background: rgba(255, 213, 106, 0.15);
  color: #ffd56a;
  border: 1px solid rgba(255, 213, 106, 0.35);
}
.resultados-ul .r-tag.ok {
  background: rgba(61, 242, 75, 0.1);
  color: #3df24b;
  border: 1px solid rgba(61, 242, 75, 0.3);
}

/* ───────── Terminal de logs ───────── */
.term-panel {
  margin-top: 18px;
  border-radius: 10px;
  overflow: hidden;
  background: #0a0d0a;
  border: 1px solid rgba(61, 242, 75, 0.25);
  box-shadow: 0 0 16px rgba(61, 242, 75, 0.08);
  font-family: ui-monospace, "JetBrains Mono", Menlo, Consolas, monospace;
}
.term-head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: linear-gradient(180deg, #15191a, #0f1213);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.term-dot {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  display: inline-block;
}
.term-dot.r {
  background: #ff5f56;
}
.term-dot.y {
  background: #ffbd2e;
}
.term-dot.g {
  background: #27c93f;
}
.term-title {
  margin-left: 10px;
  font-size: 0.78rem;
  color: rgba(240, 209, 229, 0.65);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.term-clear {
  margin-left: auto;
}
.term-body {
  margin: 0;
  padding: 12px 14px;
  max-height: 320px;
  overflow-y: auto;
  font-size: 0.82rem;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
  color: #c4d0c5;
  background: #0a0d0a;
}
.term-body::-webkit-scrollbar {
  width: 8px;
}
.term-body::-webkit-scrollbar-thumb {
  background: rgba(61, 242, 75, 0.25);
  border-radius: 4px;
}
.term-line {
  display: block;
}
.term-t {
  color: rgba(240, 209, 229, 0.4);
}
.term-arq {
  color: #f0d1e5;
  font-weight: 600;
}
.term-msg {
  color: #c4d0c5;
}
.lvl-info .term-msg {
  color: #9ccbff;
}
.lvl-ok .term-msg {
  color: #3df24b;
}
.lvl-warn .term-msg {
  color: #ffd56a;
}
.lvl-err .term-msg {
  color: #ff7a7a;
  font-weight: 600;
}
.lvl-step {
  border-left: 2px solid rgba(61, 242, 75, 0.55);
  padding-left: 6px;
  margin-left: -8px;
}
.lvl-step .term-msg {
  color: #3df24b;
  font-weight: 700;
}
</style>
