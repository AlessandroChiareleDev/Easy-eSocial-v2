/**
 * Empresa store - multi-tenant.
 *
 * Persiste a empresa selecionada no localStorage (apenas id/nome/cnpj,
 * NUNCA token). Token continua so em memoria (auth store).
 *
 * Apos login o usuario e mandado pra /empresas pra escolher; o id
 * escolhido vai automaticamente em todo request /py-api via interceptor.
 */
import { defineStore } from "pinia";
import { computed, ref } from "vue";

export interface Empresa {
  id: number;
  nome: string;
  cnpj: string;
  ativo: boolean;
  tem_dados?: boolean;
  xlsx_count?: number;
  envios_count?: number;
  db_kind?: "supabase" | "local" | string;
}

const LS_KEY = "easy_v2_empresa_atual";

function loadFromStorage(): Empresa | null {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed.id === "number") return parsed as Empresa;
  } catch {
    /* ignore */
  }
  return null;
}

export const useEmpresaStore = defineStore("empresa", () => {
  const current = ref<Empresa | null>(loadFromStorage());
  const lista = ref<Empresa[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const hasSelected = computed(() => !!current.value);
  const currentId = computed(() => current.value?.id ?? null);

  async function carregar(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const res = await fetch("/explorador-api/api/empresas", {
        headers: { Accept: "application/json" },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = (await res.json()) as { empresas: Empresa[] };
      lista.value = body.empresas ?? [];
      // se a empresa atual nao existe mais na lista, limpa
      if (
        current.value &&
        !lista.value.some((e) => e.id === current.value!.id)
      ) {
        clear();
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : "Falha ao listar empresas";
      lista.value = [];
    } finally {
      loading.value = false;
    }
  }

  function setEmpresa(emp: Empresa): void {
    current.value = emp;
    try {
      localStorage.setItem(LS_KEY, JSON.stringify(emp));
    } catch {
      /* storage cheio ou bloqueado - tudo bem, segue em memoria */
    }
  }

  function clear(): void {
    current.value = null;
    try {
      localStorage.removeItem(LS_KEY);
    } catch {
      /* ignore */
    }
  }

  return {
    current,
    lista,
    loading,
    error,
    hasSelected,
    currentId,
    carregar,
    setEmpresa,
    clear,
  };
});
