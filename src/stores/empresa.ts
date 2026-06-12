/**
 * Empresa store — multi-tenant V2 (CNPJ-based).
 *
 * A lista de empresas vem do auth store (popular no login).
 * Aqui guardamos apenas qual está ATIVA (CNPJ) — persistido em
 * localStorage. Todo request usa header X-Empresa-CNPJ via api.ts.
 */
import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { useAuthStore, type AuthEmpresa } from "./auth";

export type Empresa = AuthEmpresa;

const LS_KEY = "easy_v2_empresa_cnpj";

const LEGACY_ID_BY_CNPJ: Record<string, number> = {
  "05969071000110": 1,
  "05969071": 1,
  "09445502000109": 2,
  "09445502": 2,
  "10874523000110": 3,
  "10874523": 3,
  "64030638000158": 4,
  "64030638": 4,
};

const LEGACY_ID_BY_SCHEMA: Record<string, number> = {
  appa: 1,
  solucoes: 2,
  objetiva: 3,
  cte: 4,
};

const LEGACY_ID_BY_RAZAO: Record<string, number> = {
  appa: 1,
  solucoes: 2,
  objetiva: 3,
  cte: 4,
};

function normalizeCnpj(value: string | null | undefined): string {
  return (value ?? "").replace(/\D/g, "");
}

function normalizeKey(value: string | null | undefined): string {
  return (value ?? "").trim().toLowerCase();
}

function legacyIdForEmpresa(
  cnpj: string | null | undefined,
  schemaName?: string | null,
  razaoSocial?: string | null,
): number | null {
  const cnpjDigits = normalizeCnpj(cnpj);
  if (cnpjDigits && LEGACY_ID_BY_CNPJ[cnpjDigits]) {
    return LEGACY_ID_BY_CNPJ[cnpjDigits];
  }

  const cnpjRaiz = cnpjDigits.slice(0, 8);
  if (cnpjRaiz && LEGACY_ID_BY_CNPJ[cnpjRaiz]) {
    return LEGACY_ID_BY_CNPJ[cnpjRaiz];
  }

  const schemaKey = normalizeKey(schemaName);
  if (schemaKey && LEGACY_ID_BY_SCHEMA[schemaKey]) {
    return LEGACY_ID_BY_SCHEMA[schemaKey];
  }

  const razaoKey = normalizeKey(razaoSocial);
  if (razaoKey && LEGACY_ID_BY_RAZAO[razaoKey]) {
    return LEGACY_ID_BY_RAZAO[razaoKey];
  }

  return null;
}

function loadCnpjFromStorage(): string | null {
  try {
    const raw = localStorage.getItem(LS_KEY);
    const normalized = normalizeCnpj(raw);
    if (normalized.length > 0) return normalized;
  } catch {
    /* ignore */
  }
  return null;
}

export const useEmpresaStore = defineStore("empresa", () => {
  const currentCnpj = ref<string | null>(loadCnpjFromStorage());

  const lista = computed<Empresa[]>(() => {
    const auth = useAuthStore();
    return auth.empresas;
  });

  const current = computed<Empresa | null>(() => {
    if (!currentCnpj.value) return null;
    const currentDigits = normalizeCnpj(currentCnpj.value);
    return (
      lista.value.find((e) => normalizeCnpj(e.cnpj) === currentDigits) ?? null
    );
  });

  const hasSelected = computed(() => !!current.value);

  function setEmpresa(emp: Empresa): void {
    currentCnpj.value = normalizeCnpj(emp.cnpj);
    try {
      localStorage.setItem(LS_KEY, currentCnpj.value);
    } catch {
      /* ignore */
    }
  }

  function setEmpresaByCnpj(cnpj: string): boolean {
    const digits = normalizeCnpj(cnpj);
    const found = lista.value.find((e) => normalizeCnpj(e.cnpj) === digits);
    if (!found) return false;
    setEmpresa(found);
    return true;
  }

  function ensureValidSelection(): boolean {
    if (current.value) return true;

    if (currentCnpj.value) clear();

    const ativas = lista.value.filter((e) => e.ativo !== false);
    if (ativas.length === 1) {
      const unica = ativas[0];
      if (!unica) return false;
      setEmpresa(unica);
      return true;
    }
    return false;
  }

  function clear(): void {
    currentCnpj.value = null;
    try {
      localStorage.removeItem(LS_KEY);
    } catch {
      /* ignore */
    }
  }

  return {
    currentCnpj,
    current,
    lista,
    hasSelected,
    /**
     * V1 leftover: mapeia CNPJ -> empresa_id numerico que ainda eh aceito
     * por endpoints legados (Explorador, S-1210 anual). Default APPA=1.
     *   05969071000110 -> 1 (APPA)
     *   09445502000109 -> 2 (SOLUCOES)
     *   10874523000110 -> 3 (OBJETIVA)
     *   64030638000158 -> 4 (CTE)
     */
    currentId: computed<number | null>(() => {
      const emp = current.value;
      return legacyIdForEmpresa(
        currentCnpj.value || emp?.cnpj,
        emp?.schema_name,
        emp?.razao_social,
      );
    }),
    setEmpresa,
    setEmpresaByCnpj,
    ensureValidSelection,
    clear,
  };
});
