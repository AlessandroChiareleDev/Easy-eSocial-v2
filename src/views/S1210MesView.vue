<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  s1210CpfsDoMes,
  s1210DetalheCpf,
  urlXmlCpf,
  type DetalheCpf,
} from "@/services/exploradorApi";
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
      cpfs:
        (resp as unknown as { cpfs?: CpfRow[]; items?: CpfRow[] }).cpfs ??
        (resp as unknown as { items: CpfRow[] }).items ??
        [],
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

// ─── Detalhe do CPF (modal) ──────────────────────────────────────────
const detalhe = ref<DetalheCpf | null>(null);
const carregandoDetalhe = ref(false);
const erroDetalhe = ref<string>("");

async function abrirDetalhe(r: CpfRow) {
  detalhe.value = null;
  erroDetalhe.value = "";
  carregandoDetalhe.value = true;
  try {
    detalhe.value = await s1210DetalheCpf(
      r.lote_num,
      props.per_apur,
      r.cpf,
      empresaId.value,
    );
  } catch (e) {
    erroDetalhe.value =
      e instanceof Error ? e.message : "Falha ao carregar detalhes";
  } finally {
    carregandoDetalhe.value = false;
  }
}
function fecharDetalhe() {
  detalhe.value = null;
  erroDetalhe.value = "";
}
function fmtMoney(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}
function fmtReciboShort(r: string | null | undefined): string {
  if (!r) return "—";
  return r.length > 16 ? `…${r.slice(-16)}` : r;
}
function fmtData(s: string | null | undefined): string {
  if (!s) return "—";
  try {
    return new Date(s).toLocaleString("pt-BR");
  } catch {
    return s;
  }
}
function baixarXmlDetalhe(tipo: "S-1210" | "S-5002") {
  if (!detalhe.value) return;
  const url = urlXmlCpf(
    detalhe.value.lote_num,
    detalhe.value.per_apur,
    detalhe.value.cpf,
    empresaId.value,
    tipo,
  );
  window.open(url, "_blank");
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
            <tr
              v-for="(r, i) in linhas"
              :key="r.cpf"
              class="row-click"
              @click="abrirDetalhe(r)"
              :title="`Ver detalhamento de ${fmtCpf(r.cpf)}`"
            >
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
                  @click.stop="baixarXml(r.cpf)"
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

    <!-- ═══════ MODAL DETALHE DO CPF ═══════ -->
    <div
      v-if="detalhe || carregandoDetalhe || erroDetalhe"
      class="modal-bg"
      @click.self="fecharDetalhe"
    >
      <div class="modal modal--lg">
        <header class="modal-head">
          <div>
            <div class="modal-kicker">Detalhes do envio · S-1210</div>
            <h2 v-if="detalhe">
              {{ fmtCpf(detalhe.cpf) }}
              <span v-if="detalhe.nome" class="head-nome"
                >· {{ detalhe.nome }}</span
              >
            </h2>
            <h2 v-else>Carregando…</h2>
          </div>
          <button class="fechar" @click="fecharDetalhe">×</button>
        </header>

        <div class="modal-body">
          <div v-if="carregandoDetalhe" class="det-state">
            Buscando informações do banco e XMLs indexados…
          </div>
          <div v-else-if="erroDetalhe" class="det-state det-state--err">
            {{ erroDetalhe }}
          </div>

          <template v-else-if="detalhe">
            <!-- Badges -->
            <div class="det-badges">
              <span :class="classeStatus(detalhe.status_atual)">{{
                detalhe.status_atual
              }}</span>
              <span class="badge">{{ tituloMes }}</span>
              <span class="badge">Lote {{ detalhe.lote_num }}</span>
              <span v-if="detalhe.qtd_envios > 1" class="badge badge--hist">
                {{ detalhe.qtd_envios }} envios
              </span>
              <span
                v-if="detalhe.ind_retif_original === '2'"
                class="badge badge--ret"
              >
                Retificação (indRetif=2)
              </span>
            </div>

            <!-- Identificação -->
            <section class="det-sec">
              <h3 class="det-sec-t">👤 Identificação</h3>
              <dl class="det-kv">
                <dt>CPF</dt>
                <dd class="mono">{{ fmtCpf(detalhe.cpf) }}</dd>
                <dt>Nome</dt>
                <dd>{{ detalhe.nome ?? "—" }}</dd>
                <dt>Matrícula</dt>
                <dd class="mono">{{ detalhe.matricula ?? "—" }}</dd>
                <dt>Competência</dt>
                <dd>{{ tituloMes }}</dd>
                <dt>Empregador</dt>
                <dd class="mono">
                  CNPJ raiz {{ detalhe.empregador_cnpj_raiz || "—" }}
                </dd>
              </dl>
            </section>

            <!-- Cadeia de recibos -->
            <section class="det-sec">
              <h3 class="det-sec-t">🔗 Cadeia de recibos</h3>
              <div class="recibo-chain">
                <div class="chain-node">
                  <span class="chain-lbl">Recibo do XML indexado</span>
                  <span class="chain-val mono">{{
                    fmtReciboShort(detalhe.nr_recibo_zip)
                  }}</span>
                  <span class="chain-sub">Explorador</span>
                </div>
                <span class="chain-arr">→</span>
                <div class="chain-node chain-node--active">
                  <span class="chain-lbl">Recibo ativo</span>
                  <span class="chain-val mono">{{
                    fmtReciboShort(detalhe.nr_recibo_ativo)
                  }}</span>
                  <span class="chain-sub">
                    <template v-if="detalhe.recibo_fonte === 'cadeia'">
                      após {{ detalhe.cadeia_candidatos }} retific.
                    </template>
                    <template v-else-if="detalhe.recibo_fonte === 'zip'"
                      >mesmo do XML</template
                    >
                    <template v-else>—</template>
                  </span>
                </div>
                <span class="chain-arr">→</span>
                <div
                  class="chain-node chain-node--new"
                  :class="{
                    'chain-node--empty': !detalhe.ultimo_envio?.nr_recibo_novo,
                  }"
                >
                  <span class="chain-lbl">Último envio (novo)</span>
                  <span class="chain-val mono">{{
                    fmtReciboShort(detalhe.ultimo_envio?.nr_recibo_novo ?? null)
                  }}</span>
                  <span class="chain-sub">retorno eSocial</span>
                </div>
              </div>
            </section>

            <!-- Pagamentos -->
            <section class="det-sec">
              <h3 class="det-sec-t">
                💰 Pagamentos declarados
                <span v-if="detalhe.pagamentos.length" class="det-sec-sub">
                  {{ detalhe.pagamentos.length }} pagamento(s) · total
                  <strong>{{ fmtMoney(detalhe.total_vr_liq) }}</strong>
                </span>
              </h3>
              <div v-if="!detalhe.pagamentos.length" class="det-empty">
                Nenhum pagamento — XML S-1210 não indexado para este CPF.
              </div>
              <table v-else class="det-table">
                <thead>
                  <tr>
                    <th>Data pgto</th>
                    <th>Tipo</th>
                    <th>Per. ref</th>
                    <th>ideDmDev</th>
                    <th class="rt">Valor líquido</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(p, i) in detalhe.pagamentos" :key="i">
                    <td>{{ p.dt_pgto }}</td>
                    <td>
                      <span class="pill pill--tp">{{ p.tp_pgto }}</span>
                      {{ p.tp_pgto_label }}
                    </td>
                    <td>{{ p.per_ref ?? "—" }}</td>
                    <td class="mono small">{{ p.ide_dm_dev }}</td>
                    <td class="rt bold">{{ fmtMoney(p.vr_liq) }}</td>
                  </tr>
                </tbody>
              </table>
            </section>

            <!-- IR efetivo -->
            <section class="det-sec">
              <h3 class="det-sec-t">
                💰 IRRF retido
                <span class="det-sec-sub">
                  fonte: {{ detalhe.ir_efetivo_fonte ?? "—" }}
                </span>
              </h3>
              <div class="ir-box">
                <div class="ir-main">
                  <span class="ir-lbl">Valor retido</span>
                  <span class="ir-val">{{
                    fmtMoney(detalhe.ir_efetivo_valor)
                  }}</span>
                </div>
                <div v-if="detalhe.s5002_ativo" class="ir-s5002">
                  <div class="ir-row">
                    <span class="ir-k">Rend. tributável</span>
                    <span class="ir-v">{{
                      fmtMoney(detalhe.s5002_ativo.vlr_rend_trib)
                    }}</span>
                  </div>
                  <div class="ir-row">
                    <span class="ir-k">Prev. oficial</span>
                    <span class="ir-v">{{
                      fmtMoney(detalhe.s5002_ativo.vlr_prev_oficial)
                    }}</span>
                  </div>
                  <div class="ir-row">
                    <span class="ir-k">CRMen</span>
                    <span class="ir-v mono">{{
                      detalhe.s5002_ativo.cr_men ?? "—"
                    }}</span>
                  </div>
                  <div class="ir-row">
                    <span class="ir-k">Recibo S-5002</span>
                    <span class="ir-v mono small">{{
                      fmtReciboShort(detalhe.s5002_ativo.nr_recibo)
                    }}</span>
                  </div>
                </div>
                <div v-else-if="detalhe.zip_encontrado" class="ir-note">
                  Nenhum S-5002 indexado para este CPF no período. Suba o ZIP
                  com S-5002 no Explorador.
                </div>
              </div>

              <table
                v-if="detalhe.s5002_ativo && detalhe.s5002_ativo.info_ir.length"
                class="det-table"
                style="margin-top: 0.75rem"
              >
                <thead>
                  <tr>
                    <th>tpInfoIR</th>
                    <th>Descrição</th>
                    <th class="rt">Valor</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(it, i) in detalhe.s5002_ativo.info_ir" :key="i">
                    <td class="mono">{{ it.tp_info_ir }}</td>
                    <td>{{ it.tp_info_ir_label }}</td>
                    <td class="rt">{{ fmtMoney(it.valor) }}</td>
                  </tr>
                </tbody>
              </table>
            </section>

            <!-- infoIRCR S-1210 -->
            <section v-if="detalhe.info_ir.length" class="det-sec">
              <h3 class="det-sec-t">
                🧾 infoIRCR (do S-1210)
                <span class="det-sec-sub">declaração complementar enviada</span>
              </h3>
              <table class="det-table">
                <thead>
                  <tr>
                    <th>Código (tpCR)</th>
                    <th>Descrição</th>
                    <th class="rt">vrCR</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(ir, i) in detalhe.info_ir" :key="i">
                    <td class="mono">{{ ir.tp_cr }}</td>
                    <td>{{ ir.tp_cr_label }}</td>
                    <td class="rt">
                      <span
                        v-if="ir.vr_cr == null || ir.vr_cr === 0"
                        class="muted"
                        >não declarado</span
                      >
                      <span v-else class="bold">{{ fmtMoney(ir.vr_cr) }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </section>

            <!-- Histórico de envios -->
            <section v-if="detalhe.historico_envios.length" class="det-sec">
              <h3 class="det-sec-t">
                🕒 Histórico de envios
                <span class="det-sec-sub"
                  >{{ detalhe.historico_envios.length }} registro(s)</span
                >
              </h3>
              <div class="timeline">
                <div
                  v-for="(h, i) in [...detalhe.historico_envios].reverse()"
                  :key="i"
                  class="tl-item"
                >
                  <div class="tl-body">
                    <div class="tl-top">
                      <span :class="classeStatus(h.status)">{{
                        h.status
                      }}</span>
                      <span class="tl-data">{{ fmtData(h.enviado_em) }}</span>
                      <span v-if="h.codigo_resposta" class="pill pill--cod">
                        código {{ h.codigo_resposta }}
                      </span>
                    </div>
                    <div v-if="h.descricao_resposta" class="tl-desc">
                      {{ h.descricao_resposta }}
                    </div>
                    <div v-if="h.erro_descricao" class="tl-erro">
                      ⚠ {{ h.erro_descricao }}
                    </div>
                    <div class="tl-recibos">
                      <span v-if="h.nr_recibo_usado"
                        >usado:
                        <code class="mono">{{
                          fmtReciboShort(h.nr_recibo_usado)
                        }}</code></span
                      >
                      <span v-if="h.nr_recibo_novo"
                        >novo:
                        <code class="mono">{{
                          fmtReciboShort(h.nr_recibo_novo)
                        }}</code></span
                      >
                      <span v-if="h.protocolo"
                        >protocolo:
                        <code class="mono small">{{ h.protocolo }}</code></span
                      >
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <!-- Downloads -->
            <section class="det-sec">
              <h3 class="det-sec-t">⬇ Baixar XMLs originais</h3>
              <div class="det-downloads">
                <button
                  class="btn-xml"
                  :disabled="!detalhe.zip_encontrado"
                  @click="baixarXmlDetalhe('S-1210')"
                >
                  S-1210 enviado
                </button>
                <button
                  class="btn-xml"
                  :disabled="!detalhe.s5002_ativo"
                  @click="baixarXmlDetalhe('S-5002')"
                >
                  S-5002 (Receita)
                </button>
              </div>
            </section>

            <!-- Técnico -->
            <section class="det-sec det-sec--tec">
              <h3 class="det-sec-t">⚙ Dados técnicos</h3>
              <dl class="det-kv det-kv--small">
                <dt>tpAmb</dt>
                <dd>{{ detalhe.tp_amb }} (produção)</dd>
                <dt>indRetif</dt>
                <dd>{{ detalhe.ind_retif_original ?? "—" }}</dd>
                <dt>procEmi / verProc</dt>
                <dd>{{ detalhe.proc_emi }} · {{ detalhe.ver_proc }}</dd>
                <dt>dhProcessamento</dt>
                <dd class="mono small">
                  {{ fmtData(detalhe.dh_processamento) }}
                </dd>
                <dt v-if="detalhe.zip_erro">Aviso</dt>
                <dd v-if="detalhe.zip_erro" class="warn">
                  {{ detalhe.zip_erro }}
                </dd>
              </dl>
            </section>
          </template>
        </div>
      </div>
    </div>
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

/* ═══════ MODAL DETALHE DO CPF ═══════ */
.row-click {
  cursor: pointer;
  transition: background 0.12s ease;
}
.row-click:hover {
  background: rgba(120, 170, 255, 0.08) !important;
}
.modal-bg {
  position: fixed;
  inset: 0;
  background: rgba(6, 10, 18, 0.78);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  z-index: 9000;
  padding: 2.5rem 1rem;
  overflow-y: auto;
}
.modal {
  background: #121826;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  width: 100%;
  max-width: 980px;
  box-shadow: 0 18px 60px rgba(0, 0, 0, 0.55);
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 5rem);
}
.modal--lg {
  max-width: 1080px;
}
.modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.1rem 1.4rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}
.modal-kicker {
  font-size: 0.72rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #94a3b8;
  margin-bottom: 0.25rem;
}
.modal-head h2 {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 600;
  color: #e6edf7;
}
.head-nome {
  font-weight: 400;
  color: #94a3b8;
  font-size: 0.95rem;
}
.fechar {
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 1.6rem;
  line-height: 1;
  cursor: pointer;
  padding: 0 0.25rem;
}
.fechar:hover {
  color: #fff;
}
.modal-body {
  padding: 1rem 1.4rem 1.4rem;
  overflow-y: auto;
}
.det-state {
  padding: 2rem;
  text-align: center;
  color: #94a3b8;
}
.det-state--err {
  color: #ff9a9a;
}
.det-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
.badge {
  padding: 0.25rem 0.55rem;
  border-radius: 999px;
  font-size: 0.74rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #cdd6e3;
}
.badge--hist {
  background: rgba(120, 140, 255, 0.12);
  border-color: rgba(120, 140, 255, 0.35);
  color: #c9d3ff;
}
.badge--ret {
  background: rgba(255, 170, 80, 0.12);
  border-color: rgba(255, 170, 80, 0.35);
  color: #ffd6a0;
}
.det-sec {
  margin: 1.1rem 0;
  padding: 0.9rem 1rem;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 10px;
}
.det-sec--tec {
  background: rgba(255, 255, 255, 0.015);
}
.det-sec-t {
  margin: 0 0 0.65rem;
  font-size: 0.92rem;
  font-weight: 600;
  color: #e3e9f5;
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  flex-wrap: wrap;
}
.det-sec-sub {
  font-size: 0.74rem;
  font-weight: 400;
  color: #94a3b8;
}
.det-kv {
  display: grid;
  grid-template-columns: 160px 1fr;
  gap: 0.4rem 1rem;
  margin: 0;
  font-size: 0.86rem;
}
.det-kv--small {
  font-size: 0.78rem;
}
.det-kv dt {
  color: #94a3b8;
}
.det-kv dd {
  margin: 0;
  color: #d8e0ec;
}
.det-kv dd.warn {
  color: #ffb070;
}
.recibo-chain {
  display: flex;
  align-items: stretch;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.chain-node {
  flex: 1 1 200px;
  min-width: 180px;
  padding: 0.6rem 0.75rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 0.18rem;
}
.chain-node--active {
  background: rgba(80, 200, 160, 0.08);
  border-color: rgba(80, 200, 160, 0.35);
}
.chain-node--new {
  background: rgba(120, 140, 255, 0.06);
  border-color: rgba(120, 140, 255, 0.3);
}
.chain-node--empty {
  opacity: 0.5;
}
.chain-lbl {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #94a3b8;
}
.chain-val {
  font-size: 0.92rem;
  font-weight: 600;
  color: #e6edf7;
}
.chain-sub {
  font-size: 0.72rem;
  color: #94a3b8;
}
.chain-arr {
  align-self: center;
  color: #6b7891;
  font-size: 1.15rem;
}
.det-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.84rem;
}
.det-table th,
.det-table td {
  padding: 0.45rem 0.6rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  text-align: left;
}
.det-table th {
  color: #94a3b8;
  font-weight: 500;
  font-size: 0.74rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.det-table td.rt,
.det-table th.rt {
  text-align: right;
}
.det-table td.bold {
  font-weight: 600;
  color: #e6edf7;
}
.det-empty {
  padding: 0.75rem;
  text-align: center;
  color: #94a3b8;
  font-size: 0.85rem;
}
.pill--tp {
  background: rgba(120, 140, 255, 0.12);
  border-color: rgba(120, 140, 255, 0.35);
  color: #c9d3ff;
  font-weight: 600;
}
.pill--cod {
  background: rgba(255, 200, 80, 0.1);
  border-color: rgba(255, 200, 80, 0.3);
  color: #ffd884;
}
.ir-box {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: flex-start;
}
.ir-main {
  flex: 0 0 auto;
  padding: 0.7rem 1rem;
  background: rgba(80, 200, 160, 0.08);
  border: 1px solid rgba(80, 200, 160, 0.3);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}
.ir-lbl {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #94a3b8;
}
.ir-val {
  font-size: 1.4rem;
  font-weight: 700;
  color: #b5f0d6;
}
.ir-s5002 {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.25rem 0.85rem;
  font-size: 0.82rem;
}
.ir-k {
  color: #94a3b8;
}
.ir-v {
  color: #d8e0ec;
}
.ir-note {
  flex: 1;
  font-size: 0.82rem;
  color: #94a3b8;
  font-style: italic;
}
.timeline {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}
.tl-item {
  padding: 0.6rem 0.75rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 8px;
}
.tl-top {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex-wrap: wrap;
  margin-bottom: 0.25rem;
}
.tl-data {
  font-size: 0.78rem;
  color: #94a3b8;
}
.tl-desc {
  font-size: 0.82rem;
  color: #cdd6e3;
}
.tl-erro {
  font-size: 0.8rem;
  color: #ff9a9a;
  margin-top: 0.2rem;
}
.tl-recibos {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  font-size: 0.74rem;
  color: #94a3b8;
  margin-top: 0.3rem;
}
.tl-recibos code {
  color: #d8e0ec;
}
.det-downloads {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
}
</style>
