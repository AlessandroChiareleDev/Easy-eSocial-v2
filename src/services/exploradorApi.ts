/**
 * Cliente HTTP do Explorador — backend FastAPI em :8001 via proxy /explorador-api.
 * Não exige auth no MVP (local).
 */

const BASE = "/explorador-api";

export interface ZipRow {
  id: number;
  empresa_id: number;
  dt_ini: string;
  dt_fim: string;
  sequencial_esocial: string | null;
  nome_arquivo_original: string;
  sha256: string;
  tamanho_bytes: number;
  total_xmls: number | null;
  perapur_dominante: string | null;
  enviado_em: string;
  extraido_em: string | null;
  extracao_status: "pendente" | "extraindo" | "ok" | "erro";
  extracao_erro: string | null;
}

export interface UploadOk {
  ok: true;
  duplicado: boolean;
  zip_id: number;
  sha256: string;
  tamanho_bytes: number;
  sequencial_esocial?: string | null;
  enviado_em?: string;
  mensagem?: string;
}

export interface ExtractOk {
  ok: true;
  zip_id: number;
  total_xmls: number;
  indexados: number;
  duplicados_id_evento: number;
  falhas: number;
  perapur_dominante: string | null;
}

export interface EventoRow {
  id: number;
  tipo_evento: string;
  cpf: string | null;
  per_apur: string | null;
  nr_recibo: string | null;
  id_evento: string | null;
  referenciado_recibo: string | null;
  zip_id: number;
  xml_entry_name: string;
  nome_arquivo_original: string;
  dt_ini: string;
  dt_fim: string;
}

export interface UploadProgress {
  loaded: number;
  total: number;
  percent: number;
  /** Bytes/segundo (média móvel curta) */
  rate: number;
  /** Segundos de upload em andamento */
  elapsed: number;
  /** Estimativa em segundos restantes */
  eta: number;
}

export interface UploadStartArgs {
  file: File;
  empresaId: number;
  dtIni: string; // YYYY-MM-DD
  dtFim: string; // YYYY-MM-DD
  onProgress?: (p: UploadProgress) => void;
  /** Disparado quando 100% dos bytes foram enviados (servidor ainda processando) */
  onUploadFinished?: () => void;
  signal?: AbortSignal;
}

export interface UploadHandle {
  promise: Promise<UploadOk>;
  abort: () => void;
}

/**
 * Upload via XHR — XHR.upload.onprogress é a única API que entrega bytes
 * enviados em tempo real. fetch() não tem isso ainda.
 */
export function uploadZip(args: UploadStartArgs): UploadHandle {
  const xhr = new XMLHttpRequest();
  const fd = new FormData();
  fd.append("arquivo", args.file, args.file.name);
  fd.append("empresa_id", String(args.empresaId));
  fd.append("dt_ini", args.dtIni);
  fd.append("dt_fim", args.dtFim);

  let lastSampleAt = performance.now();
  let lastSampleLoaded = 0;
  let smoothedRate = 0;
  const startedAt = performance.now();

  const promise = new Promise<UploadOk>((resolve, reject) => {
    xhr.open("POST", `${BASE}/api/explorador/zips/upload`);

    xhr.upload.onprogress = (e) => {
      if (!e.lengthComputable) return;
      const now = performance.now();
      const dt = (now - lastSampleAt) / 1000;
      if (dt > 0.15 || e.loaded === e.total) {
        const dBytes = e.loaded - lastSampleLoaded;
        const inst = dBytes / Math.max(dt, 1e-3);
        // EMA com alpha 0.3
        smoothedRate =
          smoothedRate === 0 ? inst : 0.7 * smoothedRate + 0.3 * inst;
        lastSampleAt = now;
        lastSampleLoaded = e.loaded;
      }
      const elapsed = (now - startedAt) / 1000;
      const remaining = Math.max(e.total - e.loaded, 0);
      const eta = smoothedRate > 0 ? remaining / smoothedRate : 0;
      args.onProgress?.({
        loaded: e.loaded,
        total: e.total,
        percent: e.total ? (e.loaded / e.total) * 100 : 0,
        rate: smoothedRate,
        elapsed,
        eta,
      });
    };

    xhr.onload = () => {
      try {
        const body = JSON.parse(xhr.responseText);
        if (xhr.status >= 200 && xhr.status < 300) resolve(body as UploadOk);
        else
          reject(
            Object.assign(new Error(body?.detail || `HTTP ${xhr.status}`), {
              status: xhr.status,
              body,
            }),
          );
      } catch (e) {
        reject(new Error(`resposta inválida (${xhr.status})`));
      }
    };
    xhr.onerror = () => reject(new Error("falha de rede"));
    xhr.onabort = () => reject(new DOMException("abortado", "AbortError"));

    if (args.signal) {
      args.signal.addEventListener("abort", () => xhr.abort());
    }

    xhr.send(fd);
  });

  return { promise, abort: () => xhr.abort() };
}

async function getJson<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw Object.assign(new Error(text || `HTTP ${r.status}`), {
      status: r.status,
    });
  }
  return r.json() as Promise<T>;
}
async function postJson<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`, { method: "POST" });
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw Object.assign(new Error(text || `HTTP ${r.status}`), {
      status: r.status,
    });
  }
  return r.json() as Promise<T>;
}

export async function listarZips(empresaId: number) {
  return getJson<{ ok: true; total: number; items: ZipRow[] }>(
    `/api/explorador/zips?empresa_id=${empresaId}`,
  );
}

export async function detalheZip(zipId: number) {
  return getJson<{ ok: true; zip: ZipRow & { eventos_indexados: number } }>(
    `/api/explorador/zips/${zipId}`,
  );
}

export interface ResumoZip {
  ok: true;
  zip: Pick<
    ZipRow,
    | "id"
    | "dt_ini"
    | "dt_fim"
    | "nome_arquivo_original"
    | "total_xmls"
    | "extracao_status"
  >;
  cpfs_distintos: number;
  por_tipo: { tipo_evento: string; n: number }[];
  por_per_apur: { per_apur: string; n: number }[];
}

export async function resumoZip(zipId: number) {
  return getJson<ResumoZip>(`/api/explorador/zips/${zipId}/resumo`);
}

export async function extrairZip(zipId: number) {
  return postJson<ExtractOk>(`/api/explorador/zips/${zipId}/extrair`);
}

export async function deletarZip(zipId: number) {
  const r = await fetch(`${BASE}/api/explorador/zips/${zipId}`, {
    method: "DELETE",
  });
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw Object.assign(new Error(text || `HTTP ${r.status}`), {
      status: r.status,
    });
  }
  return r.json() as Promise<{
    ok: true;
    zip_id: number;
    eventos_apagados: number;
  }>;
}

export interface AtividadeRow {
  id: number;
  empresa_id: number;
  acao: "upload" | "exclusao" | "extracao" | "duplicado";
  zip_id: number | null;
  nome_arquivo: string | null;
  sha256: string | null;
  tamanho_bytes: number | null;
  total_xmls: number | null;
  detalhe: Record<string, unknown> | null;
  criado_em: string;
}

export async function listarAtividade(empresaId: number, limit = 200) {
  return getJson<{ ok: true; total: number; items: AtividadeRow[] }>(
    `/api/explorador/atividade?empresa_id=${empresaId}&limit=${limit}`,
  );
}

// ============================================================
// CHAIN WALK v2 — timeline mensal de S-1210
// ============================================================

export interface TimelineMesRow {
  id: number;
  per_apur: string;
  head_envio_id: number | null;
  criado_em: string;
  envios_massa: number;
  envios_total: number;
  total_sucesso: number;
  total_erro: number;
}

export interface TimelineEnvio {
  id: number;
  sequencia: number;
  tipo: "zip_inicial" | "envio_massa" | "envio_individual";
  status: "em_andamento" | "concluido" | "falhou";
  iniciado_em: string;
  finalizado_em: string | null;
  total_tentados: number;
  total_sucesso: number;
  total_erro: number;
  resumo: Record<string, unknown> | null;
}

export interface ReguaResp {
  ok: true;
  timeline_mes: {
    id: number;
    empresa_id: number;
    per_apur: string;
    head_envio_id: number | null;
    criado_em: string;
  };
  envios: TimelineEnvio[];
}

export interface EstadoEnvioItem {
  cpf: string;
  status:
    | "sucesso"
    | "erro_esocial"
    | "rejeitado_local"
    | "falha_rede"
    | "pendente";
  versao_id?: number;
  versao_anterior_id?: number | null;
  versao_nova_id?: number | null;
  nr_recibo?: string | null;
  nr_recibo_anterior?: string | null;
  nr_recibo_novo?: string | null;
  is_head?: boolean;
  erro_codigo?: string | null;
  erro_mensagem?: string | null;
}

export interface EstadoEnvioResp {
  ok: true;
  envio: TimelineEnvio & {
    timeline_mes_id: number;
    per_apur: string;
    empresa_id: number;
  };
  items: EstadoEnvioItem[];
  totais: {
    sucesso: number;
    erro_esocial: number;
    falha_rede: number;
    rejeitado_local: number;
  };
}

export interface CadeiaVersao {
  id: number;
  cpf: string;
  per_apur: string;
  tipo_evento: string;
  nr_recibo: string | null;
  nr_recibo_anterior: string | null;
  retificado_por_id: number | null;
  origem_envio_id: number | null;
  is_head: boolean;
  envio_sequencia: number | null;
  envio_tipo: string | null;
  iniciado_em: string | null;
}

export interface CadeiaTentativa {
  id: number;
  timeline_envio_id: number;
  sequencia: number;
  status: string;
  criado_em: string;
  nr_recibo_anterior: string | null;
  nr_recibo_novo: string | null;
  erro_codigo: string | null;
  erro_mensagem: string | null;
  xml_enviado_disponivel: boolean;
  xml_retorno_disponivel: boolean;
}

export interface CadeiaResp {
  ok: true;
  cpf: string;
  per_apur: string;
  tipo_evento: string;
  versoes: CadeiaVersao[];
  tentativas: CadeiaTentativa[];
}

export async function listarMesesTimeline(empresaId: number) {
  return getJson<{ ok: true; items: TimelineMesRow[] }>(
    `/api/explorador/timeline/meses?empresa_id=${empresaId}`,
  );
}

export async function reguaMes(empresaId: number, perApur: string) {
  return getJson<ReguaResp>(
    `/api/explorador/timeline?empresa_id=${empresaId}&per_apur=${encodeURIComponent(perApur)}`,
  );
}

export async function estadoEnvio(envioId: number) {
  return getJson<EstadoEnvioResp>(
    `/api/explorador/timeline/envio/${envioId}/estado`,
  );
}

// ============================================================
// S-1210 Anual Overview (v2 — espelho leve do legado)
// ============================================================
export interface S1210AnualOverview {
  ano: number;
  empresa_id?: number;
  meses: Array<{
    per_apur: string;
    lotes: Array<{
      per_apur: string;
      lote_num: number;
      total: number;
      ok: number;
      erro: number;
      enviando: number;
      pendente: number;
      na: number;
      recibo_retificado?: number;
      aceito_com_aviso?: number;
      tem_xlsx: boolean;
      estado: string;
    }>;
  }>;
}

export async function s1210AnualOverview(ano: number, empresaId: number) {
  return getJson<S1210AnualOverview>(
    `/api/s1210-repo/anual/overview?ano=${ano}&empresa_id=${empresaId}`,
  );
}

export interface S1210CpfMesItem {
  cpf: string;
  nr_recibo_atual: string | null;
  is_head: boolean;
  ultimo_envio: {
    cpf: string;
    status: string;
    nr_recibo_novo: string | null;
    erro_codigo: string | null;
    erro_mensagem: string | null;
    criado_em: string;
    timeline_envio_id: number;
  } | null;
}

export interface S1210CpfsDoMes {
  ok: boolean;
  per_apur: string;
  empresa_id: number;
  lote_num: number;
  total: number;
  items: S1210CpfMesItem[];
}

export async function s1210CpfsDoMes(
  perApur: string,
  empresaId: number,
  loteNum: number = 1,
) {
  return getJson<S1210CpfsDoMes>(
    `/api/s1210-repo/cpfs-do-mes?per_apur=${encodeURIComponent(perApur)}&empresa_id=${empresaId}&lote_num=${loteNum}`,
  );
}

export async function cadeiaCpf(args: {
  empresaId: number;
  cpf: string;
  perApur: string;
  tipoEvento?: string;
}) {
  const qs = new URLSearchParams({
    empresa_id: String(args.empresaId),
    cpf: args.cpf,
    per_apur: args.perApur,
    tipo_evento: args.tipoEvento ?? "S-1210",
  });
  return getJson<CadeiaResp>(
    `/api/explorador/timeline/cadeia?${qs.toString()}`,
  );
}

export async function listarEventos(opts: {
  empresaId: number;
  cpf?: string;
  perApur?: string;
  tipoEvento?: string;
  zipId?: number;
  limit?: number;
  offset?: number;
}) {
  const qs = new URLSearchParams();
  qs.set("empresa_id", String(opts.empresaId));
  if (opts.cpf) qs.set("cpf", opts.cpf);
  if (opts.perApur) qs.set("per_apur", opts.perApur);
  if (opts.tipoEvento) qs.set("tipo_evento", opts.tipoEvento);
  if (opts.zipId !== undefined) qs.set("zip_id", String(opts.zipId));
  if (opts.limit !== undefined) qs.set("limit", String(opts.limit));
  if (opts.offset !== undefined) qs.set("offset", String(opts.offset));
  return getJson<{ ok: true; total: number; items: EventoRow[] }>(
    `/api/explorador/eventos?${qs.toString()}`,
  );
}

export function urlXmlEvento(eventoId: number): string {
  return `${BASE}/api/explorador/eventos/${eventoId}/xml`;
}

export function urlDownloadZip(zipId: number): string {
  return `${BASE}/api/explorador/zips/${zipId}/download`;
}

// ---------- helpers UI ----------
export function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
  return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

export function formatRate(bytesPerSec: number): string {
  return `${formatBytes(bytesPerSec)}/s`;
}

export function formatSeconds(s: number): string {
  if (!isFinite(s) || s < 0) return "—";
  if (s < 60) return `${s.toFixed(0)}s`;
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  if (m < 60) return `${m}m${sec.toString().padStart(2, "0")}s`;
  const h = Math.floor(m / 60);
  return `${h}h${(m % 60).toString().padStart(2, "0")}m`;
}

// ---------- categorias de evento (para visualizar em "pastas") ----------
export interface CategoriaEvento {
  id: string;
  titulo: string;
  cor: string; // hsl
  icone: string; // emoji simples
  descricao: string;
  tipos: string[]; // códigos tipo S-1210
}

export const CATEGORIAS: CategoriaEvento[] = [
  {
    id: "tabelas",
    titulo: "Tabelas",
    cor: "180 70% 55%",
    icone: "🗂",
    descricao: "Cadastros referenciais (rubricas, lotações, empregador)",
    tipos: [
      "S-1000",
      "S-1005",
      "S-1010",
      "S-1020",
      "S-1030",
      "S-1035",
      "S-1040",
      "S-1050",
      "S-1060",
      "S-1070",
    ],
  },
  {
    id: "naoperiodicos",
    titulo: "Não-periódicos",
    cor: "200 80% 60%",
    icone: "👤",
    descricao:
      "Vida do trabalhador (admissão, alteração, afastamento, desligamento)",
    tipos: [
      "S-2190",
      "S-2200",
      "S-2205",
      "S-2206",
      "S-2210",
      "S-2220",
      "S-2230",
      "S-2240",
      "S-2245",
      "S-2250",
      "S-2260",
      "S-2298",
      "S-2299",
      "S-2300",
      "S-2306",
      "S-2399",
      "S-2400",
      "S-2405",
      "S-2410",
      "S-2416",
      "S-2418",
      "S-2420",
      "S-2500",
      "S-2501",
    ],
  },
  {
    id: "periodicos",
    titulo: "Periódicos (folha)",
    cor: "138 73% 60%",
    icone: "💰",
    descricao: "Movimentos da folha do mês (S-1200, S-1210, S-1202…)",
    tipos: [
      "S-1200",
      "S-1202",
      "S-1207",
      "S-1210",
      "S-1250",
      "S-1260",
      "S-1270",
      "S-1280",
      "S-1295",
      "S-1298",
      "S-1299",
    ],
  },
  {
    id: "totalizadores",
    titulo: "Totalizadores",
    cor: "320 65% 60%",
    icone: "🧮",
    descricao: "Bases de cálculo (FGTS, IRRF, contribuição social, DCTFWeb)",
    tipos: ["S-5001", "S-5002", "S-5003", "S-5011", "S-5012", "S-5013"],
  },
  {
    id: "exclusoes",
    titulo: "Exclusões",
    cor: "0 70% 60%",
    icone: "⛔",
    descricao: "Exclusão de eventos enviados (S-3000)",
    tipos: ["S-3000"],
  },
  {
    id: "outros",
    titulo: "Outros",
    cor: "40 60% 55%",
    icone: "❓",
    descricao: "Eventos não categorizados",
    tipos: [],
  },
];

export function categoriaDoTipo(tipo: string): CategoriaEvento {
  for (const c of CATEGORIAS) {
    if (c.tipos.includes(tipo)) return c;
  }
  return CATEGORIAS[CATEGORIAS.length - 1]; // outros
}
