<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { s1210CpfsDoMes } from "@/services/exploradorApi";
import { useEmpresaStore } from "@/stores/empresa";

const props = defineProps<{ per_apur: string; lote_num: string }>();

interface CpfRow {
  cpf: string;
  nome: string | null;
  matricula: string | null;
  lote_num: number;
  row_number: number | null;
  tem_xml: boolean;
  nr_recibo_xml: string | null;
  status: string;
  nr_recibo_usado: string | null;
  nr_recibo_novo: string | null;
  erro_codigo: string | null;
  descricao_resposta: string | null;
  erro_descricao: string | null;
  enviado_em: string | null;
}

// Bandeira semantica derivada do erro_codigo
type FlagTipo = "recibo_retificado" | "aceito_com_aviso" | null;
function flagDoCpf(r: CpfRow): FlagTipo {
  const cod = r.erro_codigo;
  if (!cod) return null;
  if (cod === "401" || cod === "459") return "recibo_retificado";
  if (cod === "202") return "aceito_com_aviso";
  return null;
}

interface Resp {
  empresa_id: number;
  per_apur: string;
  total: number;
  cpfs: CpfRow[];
}

const router = useRouter();
const empresaStore = useEmpresaStore();
const empresaId = computed<number>(() => empresaStore.currentId ?? 1);

// Empresa Soluções (id=2) é a única com XMLs indexados — só nela o botão fica ativo
const PODE_BAIXAR_XML = computed(() => empresaId.value === 2);

const loading = ref(true);
const error = ref<string | null>(null);
const data = ref<Resp | null>(null);
const filtro = ref("");
const filtroStatus = ref<string>("todos");

const MES_LABEL: Record<string, string> = {
  "01": "Janeiro",
  "02": "Fevereiro",
  "03": "Março",
  "04": "Abril",
  "05": "Maio",
  "06": "Junho",
  "07": "Julho",
  "08": "Agosto",
  "09": "Setembro",
  "10": "Outubro",
  "11": "Novembro",
  "12": "Dezembro",
};

const tituloMes = computed(() => {
  const [y, m] = props.per_apur.split("-");
  return `${MES_LABEL[m ?? ""] ?? m ?? ""} / ${y ?? ""}`;
});

const linhas = computed(() => {
  if (!data.value) return [];
  const q = filtro.value.replace(/\D/g, "");
  return data.value.cpfs.filter((r) => {
    if (filtroStatus.value !== "todos" && r.status !== filtroStatus.value)
      return false;
    if (q && !r.cpf.includes(q)) return false;
    return true;
  });
});

const contagem = computed(() => {
  if (!data.value)
    return {
      total: 0,
      ok: 0,
      erro: 0,
      pendente: 0,
      enviando: 0,
      na: 0,
      recibo_retificado: 0,
      aceito_com_aviso: 0,
    };
  const c = {
    total: data.value.total,
    ok: 0,
    erro: 0,
    pendente: 0,
    enviando: 0,
    na: 0,
    recibo_retificado: 0,
    aceito_com_aviso: 0,
  };
  for (const r of data.value.cpfs) {
    if (r.status === "ok") c.ok++;
    else if (r.status === "erro") c.erro++;
    else if (r.status === "enviando") c.enviando++;
    else if (r.status === "na") c.na++;
    else c.pendente++;
    const f = flagDoCpf(r);
    if (f === "recibo_retificado") c.recibo_retificado++;
    else if (f === "aceito_com_aviso") c.aceito_com_aviso++;
  }
  return c;
});

function fmtCpf(cpf: string): string {
  if (!cpf || cpf.length !== 11) return cpf || "—";
  return `${cpf.slice(0, 3)}.${cpf.slice(3, 6)}.${cpf.slice(6, 9)}-${cpf.slice(9)}`;
}

function classeStatus(s: string): string {
  switch (s) {
    case "ok":
      return "pill pill-ok";
    case "erro":
      return "pill pill-err";
    case "enviando":
      return "pill pill-run";
    case "na":
      return "pill pill-na";
    default:
      return "pill pill-pend";
  }
}

function baixarXml(cpf: string) {
  const url = `/py-api/api/s1210-repo/xml-cpf?per_apur=${encodeURIComponent(props.per_apur)}&cpf=${cpf}&empresa_id=${empresaId.value}`;
  // window.open dispara download via Content-Disposition
  window.open(url, "_blank");
}

async function carregar() {
  loading.value = true;
  error.value = null;
  try {
    const resp = await s1210CpfsDoMes(
      props.per_apur,
      empresaId.value,
      Number(props.lote_num),
    );
    data.value = {
      empresa_id: resp.empresa_id,
      per_apur: resp.per_apur,
      total: resp.total,
      cpfs: (resp as unknown as { cpfs?: CpfRow[]; items?: CpfRow[] }).cpfs
        ?? (resp as unknown as { items: CpfRow[] }).items
        ?? [],
    };
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Falha ao carregar CPFs";
    data.value = null;
  } finally {
    loading.value = false;
  }
}

watch([() => props.per_apur, () => props.lote_num, empresaId], carregar);
onMounted(carregar);

function voltar() {
  router.push({ name: "s1210-anual" });
}
</script>

<template>
  <div class="s1210-mes-page">
    <header class="local-topbar">
      <div class="crumb-block">
        <div class="crumb">REPOSITÓRIO · S-1210 · CPFs DO MÊS</div>
        <div class="title">
          {{ tituloMes }} · Lote {{ props.lote_num }}
          <span class="repo-pill" v-if="data"
            >{{ data.total }} CPFs no escopo</span
          >
        </div>
      </div>
      <div class="local-actions">
        <button
          class="icon-btn"
          @click="voltar"
          title="Voltar para visão anual"
        >
          ← Voltar
        </button>
        <button
          class="icon-btn"
          :disabled="loading"
          @click="carregar"
          title="Atualizar"
        >
          ⟳
        </button>
      </div>
    </header>

    <section v-if="error" class="state-err" role="alert">
      <strong>Erro:</strong> {{ error }}
    </section>

    <section v-else-if="loading" class="state-loading">
      <span class="dot" /> carregando CPFs…
    </section>

    <section v-else-if="data">
      <div class="kpi-row">
        <div class="kpi-card">
          <div class="kpi-label">Total</div>
          <div class="kpi-value">{{ contagem.total }}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">OK</div>
          <div class="kpi-value ok">{{ contagem.ok }}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Pendente</div>
          <div class="kpi-value pend">{{ contagem.pendente }}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Erro</div>
          <div class="kpi-value err">{{ contagem.erro }}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Enviando</div>
          <div class="kpi-value run">{{ contagem.enviando }}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">NA</div>
          <div class="kpi-value na">{{ contagem.na }}</div>
        </div>
        <div
          v-if="contagem.recibo_retificado > 0"
          class="kpi-card kpi-flag kpi-flag--retif"
          title="CPFs cuja resposta do eSocial foi 401-459: o recibo do S-1200 referenciado foi retificado posteriormente. Necessario reextrair recibos atualizados (ZIP novo)."
        >
          <div class="kpi-label">🔁 Recibo retificado</div>
          <div class="kpi-value retif">{{ contagem.recibo_retificado }}</div>
        </div>
        <div
          v-if="contagem.aceito_com_aviso > 0"
          class="kpi-card kpi-flag kpi-flag--aviso"
          title="CPFs com codigo 202: aceito pelo eSocial com advertencia (rubrica/deducao). Nao precisa reenviar."
        >
          <div class="kpi-label">⚠ Aceito c/ aviso</div>
          <div class="kpi-value aviso">{{ contagem.aceito_com_aviso }}</div>
        </div>
      </div>

      <div
        v-if="contagem.recibo_retificado > 0"
        class="banner-flag banner-flag--retif"
        role="status"
      >
        <strong
          >🔁 Este mês tem {{ contagem.recibo_retificado }} CPF(s) com recibo
          retificado externamente</strong
        >
        <span
          >O eSocial retornou 401-459 (“não foi localizado evento para o recibo
          informado”). É preciso reextrair os recibos atualizados via ZIP novo
          do eSocial antes de retentar.</span
        >
      </div>

      <div class="filters">
        <input
          v-model="filtro"
          type="search"
          placeholder="Filtrar por CPF…"
          class="inp"
        />
        <select v-model="filtroStatus" class="inp">
          <option value="todos">Todos os status</option>
          <option value="pendente">Pendente</option>
          <option value="ok">OK</option>
          <option value="erro">Erro</option>
          <option value="enviando">Enviando</option>
          <option value="na">NA</option>
        </select>
        <span class="muted">{{ linhas.length }} de {{ data.total }}</span>
      </div>

      <div class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th style="width: 56px">#</th>
              <th>CPF</th>
              <th>Nome</th>
              <th>Status</th>
              <th>Recibo (XML)</th>
              <th>Recibo usado</th>
              <th>Enviado em</th>
              <th style="width: 140px">Ações</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in linhas" :key="r.cpf">
              <td class="muted">{{ i + 1 }}</td>
              <td class="mono">{{ fmtCpf(r.cpf) }}</td>
              <td>{{ r.nome || "—" }}</td>
              <td>
                <span :class="classeStatus(r.status)">{{ r.status }}</span>
                <span
                  v-if="flagDoCpf(r) === 'recibo_retificado'"
                  class="flag flag--retif"
                  :title="`Codigo ${r.erro_codigo}: recibo retificado externamente. Reextrair recibos via ZIP novo.`"
                  >🔁 retif</span
                >
                <span
                  v-else-if="flagDoCpf(r) === 'aceito_com_aviso'"
                  class="flag flag--aviso"
                  :title="`Codigo 202: aceito pelo eSocial com advertencia.`"
                  >⚠ aviso</span
                >
              </td>
              <td class="mono small">{{ r.nr_recibo_xml || "—" }}</td>
              <td class="mono small">{{ r.nr_recibo_usado || "—" }}</td>
              <td class="small">
                {{
                  r.enviado_em
                    ? new Date(r.enviado_em).toLocaleString("pt-BR")
                    : "—"
                }}
              </td>
              <td>
                <button
                  class="btn-xml"
                  :disabled="!PODE_BAIXAR_XML || !r.tem_xml"
                  :title="
                    PODE_BAIXAR_XML
                      ? r.tem_xml
                        ? 'Baixar XML de retorno do eSocial'
                        : 'XML não indexado para este CPF'
                      : 'Disponível apenas para empresa Soluções'
                  "
                  @click="baixarXml(r.cpf)"
                >
                  ⬇ XML
                </button>
              </td>
            </tr>
            <tr v-if="!linhas.length">
              <td colspan="8" class="muted center pad">
                Nenhum CPF corresponde aos filtros.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.s1210-mes-page {
  padding: 16px 24px;
}
.local-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  margin-bottom: 16px;
}
.crumb {
  font-size: 11px;
  letter-spacing: 0.12em;
  opacity: 0.7;
}
.title {
  font-size: 22px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 12px;
}
.repo-pill {
  font-size: 11px;
  padding: 3px 10px;
  background: rgba(80, 180, 120, 0.15);
  color: #6cf0a0;
  border-radius: 999px;
}
.local-actions {
  display: flex;
  gap: 8px;
}
.icon-btn {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: inherit;
  padding: 6px 14px;
  border-radius: 8px;
  cursor: pointer;
}
.icon-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.12);
}
.state-err {
  background: rgba(220, 80, 80, 0.12);
  border: 1px solid rgba(220, 80, 80, 0.3);
  padding: 12px 16px;
  border-radius: 8px;
  color: #ffaaaa;
}
.state-loading {
  padding: 20px;
  opacity: 0.7;
}
.dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #6cf0a0;
  margin-right: 8px;
  animation: pulse 1s infinite;
}
@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}

.kpi-row {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.kpi-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 12px 16px;
}
.kpi-label {
  font-size: 11px;
  opacity: 0.7;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.kpi-value {
  font-size: 22px;
  font-weight: 700;
  margin-top: 4px;
}
.kpi-value.ok {
  color: #6cf0a0;
}
.kpi-value.err {
  color: #ff8080;
}
.kpi-value.pend {
  color: #ffd060;
}
.kpi-value.run {
  color: #80c0ff;
}
.kpi-value.na {
  color: #b0b0b0;
}

.filters {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
}
.inp {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: inherit;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
}
.inp:focus {
  outline: none;
  border-color: rgba(108, 240, 160, 0.5);
}
.muted {
  opacity: 0.6;
  font-size: 12px;
}

.tbl-wrap {
  overflow: auto;
  max-height: calc(100vh - 360px);
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.tbl thead {
  position: sticky;
  top: 0;
  background: rgba(20, 20, 28, 0.95);
  backdrop-filter: blur(8px);
  z-index: 1;
}
.tbl th {
  padding: 10px 12px;
  text-align: left;
  font-weight: 600;
  opacity: 0.8;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.tbl td {
  padding: 8px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}
.tbl tbody tr:hover {
  background: rgba(255, 255, 255, 0.03);
}
.mono {
  font-family: ui-monospace, "SF Mono", monospace;
}
.small {
  font-size: 12px;
  opacity: 0.85;
}
.center {
  text-align: center;
}
.pad {
  padding: 32px;
}

.pill {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.pill-ok {
  background: rgba(80, 200, 120, 0.18);
  color: #6cf0a0;
}
.pill-err {
  background: rgba(220, 80, 80, 0.18);
  color: #ff9090;
}
.pill-pend {
  background: rgba(255, 200, 80, 0.15);
  color: #ffd060;
}
.pill-run {
  background: rgba(80, 160, 240, 0.18);
  color: #80c0ff;
}
.pill-na {
  background: rgba(160, 160, 160, 0.15);
  color: #c0c0c0;
}

.btn-xml {
  background: rgba(108, 240, 160, 0.12);
  border: 1px solid rgba(108, 240, 160, 0.3);
  color: #6cf0a0;
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  font-weight: 600;
}
.btn-xml:hover:not(:disabled) {
  background: rgba(108, 240, 160, 0.22);
}
.btn-xml:disabled {
  opacity: 0.35;
  cursor: not-allowed;
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.4);
}

/* Flags semanticas */
.flag {
  display: inline-block;
  margin-left: 6px;
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  vertical-align: middle;
  cursor: help;
}
.flag--retif {
  background: rgba(255, 130, 80, 0.18);
  color: #ffaa70;
  border: 1px solid rgba(255, 130, 80, 0.35);
}
.flag--aviso {
  background: rgba(255, 200, 80, 0.18);
  color: #ffd060;
  border: 1px solid rgba(255, 200, 80, 0.35);
}
.kpi-card.kpi-flag {
  cursor: help;
}
.kpi-flag--retif {
  border: 1px solid rgba(255, 130, 80, 0.35);
  background: rgba(255, 130, 80, 0.06);
}
.kpi-flag--aviso {
  border: 1px solid rgba(255, 200, 80, 0.35);
  background: rgba(255, 200, 80, 0.06);
}
.kpi-value.retif {
  color: #ffaa70;
}
.kpi-value.aviso {
  color: #ffd060;
}
.banner-flag {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 16px;
  border-radius: 8px;
  margin: 12px 0;
  font-size: 13px;
  line-height: 1.4;
}
.banner-flag--retif {
  background: rgba(255, 130, 80, 0.08);
  border: 1px solid rgba(255, 130, 80, 0.32);
  color: #ffc6a0;
}
.banner-flag strong {
  color: #ffaa70;
}
</style>
