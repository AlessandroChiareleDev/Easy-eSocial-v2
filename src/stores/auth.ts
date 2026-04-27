/**
 * Auth store — Pinia
 *
 * REGRA DURA (SECURITY.md):
 *  - Token JWT vive APENAS em memória (este store)
 *  - NUNCA em localStorage / sessionStorage
 *  - Reload da página → re-login obrigatório
 *  - Migrar pra httpOnly cookie + CSRF assim que o backend antigo suportar
 */

import { defineStore } from "pinia";
import { computed, ref } from "vue";

export interface AuthUser {
  id?: number | string;
  username: string;
  role?: string;
  nome?: string;
  email?: string;
  [key: string]: unknown;
}

interface LoginResponse {
  token: string;
  user: AuthUser;
}

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string | null>(null);
  const user = ref<AuthUser | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const isAuthenticated = computed(() => !!token.value);
  const initials = computed(() => {
    const src = user.value?.nome || user.value?.username || "";
    const parts = src.trim().split(/\s+/).slice(0, 2);
    return parts.map((p) => p[0]?.toUpperCase() ?? "").join("") || "??";
  });

  async function login(username: string, senha: string): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      // Import dinâmico evita ciclo (api.ts importa este store)
      const { api } = await import("@/services/api");
      const res = await api.post<LoginResponse>(
        "/auth/login",
        { username, senha },
        { skipAuth: true },
      );
      token.value = res.token;
      user.value = res.user;
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Falha no login";
      error.value = msg;
      token.value = null;
      user.value = null;
      throw e;
    } finally {
      loading.value = false;
    }
  }

  function clear(): void {
    token.value = null;
    user.value = null;
    error.value = null;
  }

  return {
    token,
    user,
    loading,
    error,
    isAuthenticated,
    initials,
    login,
    clear,
  };
});
