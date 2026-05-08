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
    /** @deprecated V1 leftover: views S1210Anual/Mes ainda usam currentId */
    currentId: computed<number | null>(() => null),
    setEmpresa,
    setEmpresaByCnpj,
    clear,
  };
});
