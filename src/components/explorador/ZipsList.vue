<script setup lang="ts">
import { computed, ref } from "vue";
import {
  formatBytes,
  urlDownloadZip,
  extrairZip,
  deletarZip,
  analisarS5002,
  reuploadZip,
  type ZipRow,
  type AnaliseS5002Resp,
} from "@/services/exploradorApi";

const props = defineProps<{ zips: ZipRow[]; empresaId?: number }>();
const emit = defineEmits<{
  (e: "visualizar", zip: ZipRow): void;
  (e: "refresh"): void;
}>();

const extraindo = ref<Set<number>>(new Set());
const extracaoErro = ref<Map<number, string>>(new Map());
const excluindo = ref<Set<number>>(new Set());
const reuploadAndamento = ref<Map<number, number>>(new Map()); // zip_id → pct

// === Multi-select para batch "Só S-5002" ===
const selecionados = ref<Set<number>>(new Set());
function toggleSelecionado(id: number) {
  if (selecionados.value.has(id)) selecionados.value.delete(id);
  else selecionados.value.add(id);
  selecionados.value = new Set(selecionados.value);
}
function limparSelecao() {
  selecionados.value = new Set();
}
function selecionarTodosOk() {
  const novos = new Set(selecionados.value);
  for (const z of props.zips) {
    if (z.extracao_status === "ok") novos.add(z.id);
  }
  selecionados.value = novos;
}

// === Batch "Só S-5002" + análise ===
const batchRodando = ref(false);
const batchProgresso = ref<{ feitos: number; total: number; atual: string }>({
  feitos: 0,
  total: 0,
  atual: "",
});
const batchErros = ref<{ zip_id: number; nome: string; erro: string }[]>([]);
const analiseResultado = ref<AnaliseS5002Resp | null>(null);
const analiseErro = ref<string | null>(null);
const mostrarModal = ref(false);

async function rodarBatchS5002() {
  if (batchRodando.value) return;
  const ids = [...selecionados.value];
  if (ids.length === 0) return;
  const zipsAlvo = props.zips.filter((z) => ids.includes(z.id));
  const ok = window.confirm(
    `Re-extrair APENAS S-5002 de ${zipsAlvo.length} zip(s)?\n\n` +
      zipsAlvo
        .map(
          (z) =>
            `• ${z.nome_arquivo_original}  (${z.perapur_dominante ?? z.dt_ini.slice(0, 7)})`,
        )
        .join("\n") +
      `\n\nOs eventos S-1210 NÃO serão tocados. Após a re-extração, ` +
      `vou rodar a análise de cobertura de S-5002 por CPF.`,
  );
  if (!ok) return;

  batchRodando.value = true;
  batchErros.value = [];
  analiseResultado.value = null;
  analiseErro.value = null;
  mostrarModal.value = true;
  batchProgresso.value = { feitos: 0, total: zipsAlvo.length, atual: "" };

  // sequencial — extração é cara, evita estourar pool/conexões
  for (const z of zipsAlvo) {
    batchProgresso.value = {
      feitos: batchProgresso.value.feitos,
      total: zipsAlvo.length,
      atual: z.nome_arquivo_original,
    };
    try {
      await extrairZip(z.id, {
        somenteS5002: true,
        empresaId: props.empresaId,
      });
    } catch (e) {
      batchErros.value.push({
        zip_id: z.id,
        nome: z.nome_arquivo_original,
        erro: (e as Error).message,
      });
    }
    batchProgresso.value = {
      feitos: batchProgresso.value.feitos + 1,
      total: zipsAlvo.length,
      atual: z.nome_arquivo_original,
    };
  }

  // análise (sempre tenta, mesmo se alguns falharam)
  if (props.empresaId !== undefined) {
    try {
      const r = await analisarS5002(props.empresaId, ids);
      analiseResultado.value = r;
    } catch (e) {
      analiseErro.value = (e as Error).message;
    }
  } else {
    analiseErro.value = "empresa_id ausente — não foi possível rodar análise.";
  }

  batchRodando.value = false;
  emit("refresh");
}

function fecharModal() {
  if (batchRodando.value) return;
  mostrarModal.value = false;
}

function copiarCpfs(lista: string[]) {
  try {
    navigator.clipboard.writeText(lista.join("\n"));
  } catch {
    // silencioso
  }
}

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

async function disparaReupload(z: ZipRow) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".zip,application/zip";
  input.onchange = async () => {
    const file = input.files?.[0];
    if (!file) return;
    // Tamanho deve bater (validação cliente, server também valida)
    let forcar = false;
    if (z.tamanho_bytes && file.size !== z.tamanho_bytes) {
      const ok = window.confirm(
        `O arquivo selecionado tem ${formatBytes(file.size)}, mas o card ` +
          `registra ${formatBytes(z.tamanho_bytes)}.\n\n` +
          `Provavelmente é um ZIP diferente. Deseja mesmo assim sobrescrever ` +
          `(forçar)? Os metadados (sha256, tamanho) serão atualizados.`,
      );
      if (!ok) return;
      forcar = true;
    }
    reuploadAndamento.value.set(z.id, 0);
    reuploadAndamento.value = new Map(reuploadAndamento.value);
    extracaoErro.value.delete(z.id);
    try {
      await reuploadZip(z.id, file, forcar, (pct) => {
        reuploadAndamento.value.set(z.id, pct);
        reuploadAndamento.value = new Map(reuploadAndamento.value);
      });
      emit("refresh");
    } catch (e) {
      const msg = (e as Error).message;
      // Se falhou por sha diferente, oferece forçar
      if (!forcar && /SHA-256/i.test(msg)) {
        const ok2 = window.confirm(
          msg +
            `\n\nDeseja sobrescrever mesmo assim (forçar)? O card vai apontar para o novo ZIP.`,
        );
        if (ok2) {
          try {
            await reuploadZip(z.id, file, true, (pct) => {
              reuploadAndamento.value.set(z.id, pct);
              reuploadAndamento.value = new Map(reuploadAndamento.value);
            });
            emit("refresh");
          } catch (e2) {
            extracaoErro.value.set(z.id, (e2 as Error).message);
            extracaoErro.value = new Map(extracaoErro.value);
          }
        }
      } else {
        extracaoErro.value.set(z.id, msg);
        extracaoErro.value = new Map(extracaoErro.value);
      }
    } finally {
      reuploadAndamento.value.delete(z.id);
      reuploadAndamento.value = new Map(reuploadAndamento.value);
    }
  };
  input.click();
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

const okZipsCount = computed(
  () => props.zips.filter((z) => z.extracao_status === "ok").length,
);
const selecaoCount = computed(() => selecionados.value.size);
</script>

<template>
  <div v-if="zips.length === 0" class="empty liquid-glass">
    <div class="empty-icon">📁</div>
    <div class="empty-title">Nenhum zip enviado ainda</div>
    <div class="empty-sub">Suba o primeiro arquivo acima para começar.</div>
  </div>

  <template v-else>
    <!-- Barra de ação batch S-5002 -->
    <div v-if="okZipsCount > 0" class="batch-bar liquid-glass">
      <div class="bb-left">
        <span class="bb-title">🔄 Batch S-5002</span>
        <span class="bb-sub">
          Selecione 1+ zips indexados para enriquecer S-5002 e rodar análise de
          cobertura por CPF.
        </span>
      </div>
      <div class="bb-right">
        <span class="bb-count">
          {{ selecaoCount }} selecionado{{ selecaoCount === 1 ? "" : "s" }}
        </span>
        <button
          class="btn-ghost btn-sm"
          :disabled="batchRodando || okZipsCount === 0"
          @click="selecionarTodosOk"
          title="Marca todos os zips com status 'indexado'"
        >
          Todos ok
        </button>
        <button
          class="btn-ghost btn-sm"
          :disabled="batchRodando || selecaoCount === 0"
          @click="limparSelecao"
        >
          Limpar
        </button>
        <button
          class="btn-primary btn-sm"
          :disabled="batchRodando || selecaoCount === 0"
          @click="rodarBatchS5002"
        >
          {{
            batchRodando
              ? "… rodando"
              : `🔄 Re-extrair S-5002 (${selecaoCount}) + analisar`
          }}
        </button>
      </div>
    </div>

    <div class="grid">
      <div
        v-for="z in zipsOrdenados"
        :key="z.id"
        class="zip-card liquid-glass"
        :class="{ 'is-selected': selecionados.has(z.id) }"
      >
        <div class="zc-head">
          <label
            v-if="z.extracao_status === 'ok'"
            class="zc-check"
            :title="'Selecionar para batch S-5002'"
          >
            <input
              type="checkbox"
              :checked="selecionados.has(z.id)"
              :disabled="batchRodando"
              @change="toggleSelecionado(z.id)"
            />
          </label>
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
            v-if="z.extracao_status === 'erro'"
            class="btn-ghost btn-reupload"
            :disabled="reuploadAndamento.has(z.id)"
            @click="disparaReupload(z)"
            :title="'Re-envia o mesmo ZIP para recuperar o card (substitui o Large Object perdido).'"
          >
            <template v-if="reuploadAndamento.has(z.id)">
              📤 enviando… {{ Math.floor(reuploadAndamento.get(z.id) ?? 0) }}%
            </template>
            <template v-else>📤 Re-upload do ZIP</template>
          </button>
          <button
            v-if="z.extracao_status === 'ok'"
            class="btn-ghost"
            :disabled="extraindo.has(z.id) || batchRodando"
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

    <!-- Modal de progresso + análise -->
    <div v-if="mostrarModal" class="modal-overlay" @click.self="fecharModal">
      <div class="modal liquid-glass">
        <div class="modal-head">
          <h3>
            {{
              batchRodando
                ? "🔄 Re-extraindo S-5002…"
                : analiseResultado
                  ? "📊 Análise de cobertura S-5002"
                  : "⚠ Resultado"
            }}
          </h3>
          <button
            class="btn-ghost btn-sm"
            :disabled="batchRodando"
            @click="fecharModal"
          >
            ✕
          </button>
        </div>

        <div class="modal-body">
          <!-- Progresso -->
          <div
            v-if="batchRodando || batchProgresso.feitos < batchProgresso.total"
            class="progress"
          >
            <div class="progress-bar">
              <div
                class="progress-fill"
                :style="{
                  width:
                    batchProgresso.total > 0
                      ? (batchProgresso.feitos / batchProgresso.total) * 100 +
                        '%'
                      : '0%',
                }"
              ></div>
            </div>
            <div class="progress-text">
              {{ batchProgresso.feitos }} / {{ batchProgresso.total }} zips
              <span v-if="batchProgresso.atual" class="mono">
                · {{ batchProgresso.atual }}
              </span>
            </div>
          </div>

          <!-- Erros de extração -->
          <div v-if="batchErros.length > 0" class="erros-box">
            <strong>⚠ {{ batchErros.length }} zip(s) falharam:</strong>
            <ul>
              <li v-for="e in batchErros" :key="e.zip_id">
                <span class="mono">{{ e.nome }}</span
                >: {{ e.erro }}
              </li>
            </ul>
          </div>

          <div v-if="analiseErro" class="erros-box">
            <strong>⚠ análise falhou:</strong> {{ analiseErro }}
          </div>

          <!-- Resultado -->
          <div v-if="analiseResultado" class="analise">
            <div class="totais-cards">
              <div class="tot-card">
                <div class="tot-lbl">CPFs S-1210</div>
                <div class="tot-val">
                  {{ analiseResultado.totais.cpfs_s1210 }}
                </div>
              </div>
              <div class="tot-card">
                <div class="tot-lbl">CPFs S-5002</div>
                <div class="tot-val">
                  {{ analiseResultado.totais.cpfs_s5002 }}
                </div>
              </div>
              <div class="tot-card ok">
                <div class="tot-lbl">S-5002 enriquecidos</div>
                <div class="tot-val">
                  {{ analiseResultado.totais.cpfs_s5002_ricos }}
                </div>
              </div>
              <div class="tot-card warn">
                <div class="tot-lbl">S-5002 pobres</div>
                <div class="tot-val">
                  {{ analiseResultado.totais.cpfs_s5002_pobres }}
                </div>
              </div>
              <div class="tot-card err">
                <div class="tot-lbl">CPFs sem S-5002</div>
                <div class="tot-val">
                  {{ analiseResultado.totais.cpfs_faltando_s5002 }}
                </div>
              </div>
            </div>

            <table class="tab-perapur">
              <thead>
                <tr>
                  <th>perApur</th>
                  <th>S-1210</th>
                  <th>S-5002</th>
                  <th>ricos</th>
                  <th>pobres</th>
                  <th>faltando</th>
                  <th>amostras</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in analiseResultado.por_perapur" :key="r.per_apur">
                  <td class="mono">{{ r.per_apur }}</td>
                  <td class="mono">{{ r.cpfs_s1210 }}</td>
                  <td class="mono">{{ r.cpfs_s5002 }}</td>
                  <td class="mono ok">{{ r.cpfs_s5002_ricos }}</td>
                  <td class="mono warn">{{ r.cpfs_s5002_pobres }}</td>
                  <td class="mono err">{{ r.cpfs_faltando_s5002 }}</td>
                  <td class="amostras">
                    <button
                      v-if="r.amostra_faltando.length > 0"
                      class="btn-ghost btn-xs"
                      :title="r.amostra_faltando.join('\n')"
                      @click="copiarCpfs(r.amostra_faltando)"
                    >
                      📋 {{ r.amostra_faltando.length }} faltando
                    </button>
                    <button
                      v-if="r.amostra_pobre.length > 0"
                      class="btn-ghost btn-xs"
                      :title="r.amostra_pobre.join('\n')"
                      @click="copiarCpfs(r.amostra_pobre)"
                    >
                      📋 {{ r.amostra_pobre.length }} pobres
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </template>
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

/* === Batch bar S-5002 === */
.batch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 16px;
  margin-bottom: 14px;
  border-radius: 14px;
  border: 1px solid rgba(61, 242, 75, 0.18);
}
.bb-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.bb-title {
  color: #3df24b;
  font-weight: 700;
  font-size: 0.95rem;
}
.bb-sub {
  color: rgba(240, 209, 229, 0.7);
  font-size: 0.8rem;
}
.bb-right {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.bb-count {
  color: rgba(240, 209, 229, 0.85);
  font-size: 0.85rem;
  font-variant-numeric: tabular-nums;
  padding: 0 4px;
}
.btn-sm {
  padding: 7px 12px;
  font-size: 0.85rem;
  flex: initial;
}
.btn-xs {
  padding: 4px 8px;
  font-size: 0.75rem;
  flex: initial;
}

.zip-card.is-selected {
  border: 1px solid rgba(61, 242, 75, 0.55);
  box-shadow: 0 0 18px rgba(61, 242, 75, 0.18);
}
.zc-check {
  display: inline-flex;
  align-items: center;
  cursor: pointer;
  margin-right: 6px;
}
.zc-check input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: #3df24b;
  cursor: pointer;
}

/* === Modal === */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}
.modal {
  max-width: 980px;
  width: 100%;
  max-height: 88vh;
  overflow-y: auto;
  border-radius: 16px;
  padding: 20px;
}
.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.modal-head h3 {
  margin: 0;
  color: #fff;
  font-size: 1.15rem;
}
.modal-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.progress {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.progress-bar {
  background: rgba(255, 255, 255, 0.06);
  height: 10px;
  border-radius: 999px;
  overflow: hidden;
}
.progress-fill {
  background: linear-gradient(90deg, #3df24b, #9ff7a6);
  height: 100%;
  transition: width 200ms ease;
}
.progress-text {
  color: rgba(240, 209, 229, 0.8);
  font-size: 0.85rem;
}
.progress-text .mono {
  color: rgba(240, 209, 229, 0.6);
}

.erros-box {
  background: rgba(255, 80, 80, 0.08);
  border: 1px solid rgba(255, 80, 80, 0.3);
  color: #ffb3b3;
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 0.85rem;
}
.erros-box ul {
  margin: 6px 0 0;
  padding-left: 18px;
}

.totais-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px;
}
.tot-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(240, 209, 229, 0.15);
  border-radius: 10px;
  padding: 10px 12px;
}
.tot-lbl {
  font-size: 0.72rem;
  color: rgba(240, 209, 229, 0.65);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.tot-val {
  color: #fff;
  font-size: 1.4rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  margin-top: 2px;
}
.tot-card.ok .tot-val {
  color: #3df24b;
}
.tot-card.warn .tot-val {
  color: #ffd56a;
}
.tot-card.err .tot-val {
  color: #ff8a8a;
}

.tab-perapur {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}
.tab-perapur th,
.tab-perapur td {
  padding: 8px 10px;
  text-align: left;
  border-bottom: 1px solid rgba(240, 209, 229, 0.08);
}
.tab-perapur th {
  color: rgba(240, 209, 229, 0.6);
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.72rem;
  letter-spacing: 0.05em;
}
.tab-perapur td {
  color: #fff;
}
.tab-perapur td.ok {
  color: #3df24b;
}
.tab-perapur td.warn {
  color: #ffd56a;
}
.tab-perapur td.err {
  color: #ff8a8a;
}
.amostras {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
</style>
