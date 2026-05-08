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

function loadCnpjFromStorage(): string | null {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (typeof raw === "string" && raw.length > 0) return raw;
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
    return lista.value.find((e) => e.cnpj === currentCnpj.value) ?? null;
  });

  const hasSelected = computed(() => !!current.value);

  function setEmpresa(emp: Empresa): void {
    currentCnpj.value = emp.cnpj;
    try {
      localStorage.setItem(LS_KEY, emp.cnpj);
    } catch {
      /* ignore */
    }
  }

  function setEmpresaByCnpj(cnpj: string): boolean {
    const found = lista.value.find((e) => e.cnpj === cnpj);
    if (!found) return false;
    setEmpresa(found);
    return true;
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
     */
    currentId: computed<number | null>(() => {
      const cnpj = currentCnpj.value;
      if (!cnpj) return null;
      if (cnpj === "05969071000110") return 1;
      if (cnpj === "09445502000109") return 2;
      // Fallback por schema_name
      const sch = current.value?.schema_name;
      if (sch === "appa") return 1;
      if (sch === "solucoes") return 2;
      return null;
    }),
    setEmpresa,
    setEmpresaByCnpj,
    clear,
  };
});
