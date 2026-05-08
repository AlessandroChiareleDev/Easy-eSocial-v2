/**
 * Auth store — Pinia (V2 multi-tenant)
 *
 * Persiste token + user + empresas em localStorage (per BIBLIA F9.2).
 * Limpa em logout/erro 401.
 */
import { defineStore } from "pinia";
import { computed, ref } from "vue";

export interface AuthUser {
  id: string;
  email: string;
  nome?: string | null;
  super_admin?: boolean;
}

export interface AuthEmpresa {
  cnpj: string;
  razao_social?: string | null;
  schema_name?: string;
  papel: "admin" | "operador" | "leitor" | string;
  ativo?: boolean;
}

interface LoginResponse {
  token: string;
  user: AuthUser;
  empresas: AuthEmpresa[];
}

const LS_KEY = "easy_v2_auth";

interface PersistedAuth {
  token: string;
  user: AuthUser;
  empresas: AuthEmpresa[];
}

function loadFromStorage(): PersistedAuth | null {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PersistedAuth;
    if (parsed && typeof parsed.token === "string" && parsed.user) {
      return parsed;
    }
  } catch {
    /* ignore */
  }
  return null;
}

function saveToStorage(data: PersistedAuth): void {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(data));
  } catch {
    /* ignore quota */
  }
}

export const useAuthStore = defineStore("auth", () => {
  const persisted = loadFromStorage();
  const token = ref<string | null>(persisted?.token ?? null);
  const user = ref<AuthUser | null>(persisted?.user ?? null);
  const empresas = ref<AuthEmpresa[]>(persisted?.empresas ?? []);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const isAuthenticated = computed(() => !!token.value);
  const isSuperAdmin = computed(() => !!user.value?.super_admin);
  const initials = computed(() => {
    const src = user.value?.nome || user.value?.email || "";
    const parts = src.trim().split(/[\s@.]+/).slice(0, 2);
    return parts.map((p) => p[0]?.toUpperCase() ?? "").join("") || "??";
  });

  async function login(email: string, password: string): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const { api } = await import("@/services/api");
      const res = await api.post<LoginResponse>(
        "/auth/login",
        { email, password },
        { skipAuth: true },
      );
      token.value = res.token;
      user.value = res.user;
      empresas.value = res.empresas ?? [];
      saveToStorage({
        token: res.token,
        user: res.user,
        empresas: empresas.value,
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Falha no login";
      error.value = msg;
      clear();
      throw e;
    } finally {
      loading.value = false;
    }
  }

  function clear(): void {
    token.value = null;
    user.value = null;
    empresas.value = [];
    error.value = null;
    try {
      localStorage.removeItem(LS_KEY);
    } catch {
      /* ignore */
    }
  }

  return {
    token,
    user,
    empresas,
    loading,
    error,
    isAuthenticated,
    isSuperAdmin,
    initials,
    login,
    clear,
  };
});
