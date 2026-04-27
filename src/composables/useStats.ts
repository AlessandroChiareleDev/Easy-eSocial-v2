/**
 * Stats agregados pro Painel — busca em /api/tables e endpoints relacionados
 * pra alimentar as métricas flutuantes ao redor do cérebro e os opt-cards.
 *
 * Falha graciosa: se o backend tá offline, mantém os valores como null
 * (UI mostra '—').
 */

import { ref, onMounted } from "vue";
import { api } from "@/services/api";

interface TablesResponse {
  tables?: Array<{ name: string; rowCount?: number }>;
  // formato pode variar — backend antigo retorna { tables: [...] } ou array direto
}

export interface PainelStats {
  totalCpfs: number | null;
  pctOk: number | null;
  pendentes: number | null;
  ultimoPeriodo: string | null;
  totalTabelas: number | null;
  totalLotes: number | null;
  totalLogs: number | null;
}

export function useStats() {
  const stats = ref<PainelStats>({
    totalCpfs: null,
    pctOk: null,
    pendentes: null,
    ultimoPeriodo: null,
    totalTabelas: null,
    totalLotes: null,
    totalLogs: null,
  });
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function load() {
    loading.value = true;
    error.value = null;
    try {
      // Lista de tabelas disponíveis
      const tablesRes = await api
        .get<TablesResponse | Array<{ name: string }>>("/tables")
        .catch(() => null);

      if (tablesRes) {
        const list = Array.isArray(tablesRes)
          ? tablesRes
          : (tablesRes.tables ?? []);
        stats.value.totalTabelas = list.length;
      }

      // Resumo de validações (pendências = divergências abertas)
      const resumoRes = await api
        .get<{
          total?: number;
          totals?: number;
          divergencias?: number;
          pending?: number;
          corrected?: number;
          verified?: number;
          ok?: number;
          pct_ok?: number;
        }>("/validacao/resumo")
        .catch(() => null);

      if (resumoRes) {
        const total = resumoRes.total ?? resumoRes.totals ?? null;
        const pending = resumoRes.divergencias ?? resumoRes.pending ?? null;
        const ok =
          resumoRes.ok ??
          (resumoRes.corrected != null && resumoRes.verified != null
            ? resumoRes.corrected + resumoRes.verified
            : null);
        if (typeof total === "number") stats.value.totalCpfs = total;
        if (typeof pending === "number") stats.value.pendentes = pending;
        if (typeof resumoRes.pct_ok === "number") {
          stats.value.pctOk = resumoRes.pct_ok;
        } else if (typeof total === "number" && total > 0 && ok != null) {
          stats.value.pctOk = (ok / total) * 100;
        }
      }

      // Atividades / logs do admin
      const ativRes = await api
        .get<{
          total?: number;
          atividades?: unknown[];
        }>("/admin/atividades?limit=1")
        .catch(() => null);

      if (ativRes && typeof ativRes.total === "number") {
        stats.value.totalLogs = ativRes.total;
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : "Falha ao carregar stats";
    } finally {
      loading.value = false;
    }
  }

  onMounted(load);

  return { stats, loading, error, reload: load };
}
