/**
 * Cliente HTTP fino — proxy /api → backend FastAPI V2 :8000 (via vite.config).
 *
 * Auto-injeta:
 *  - Authorization: Bearer <token> (do auth store)
 *  - X-Empresa-CNPJ: <cnpj-ativo> (do empresa store)
 *
 * Erros 401 disparam logout automático.
 */

import { useAuthStore } from "@/stores/auth";
import { useEmpresaStore } from "@/stores/empresa";

export interface ApiError extends Error {
  status: number;
  body?: unknown;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
  body?: unknown;
  headers?: Record<string, string>;
  /** Pula o header Authorization (usar em /auth/login) */
  skipAuth?: boolean;
  /** Pula injeção automática do X-Empresa-CNPJ */
  skipTenant?: boolean;
  /** Override manual do CNPJ (raro — super admin) */
  cnpj?: string;
}

const BASE = "/api";

async function request<T = unknown>(
  path: string,
  opts: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(opts.headers ?? {}),
  };

  if (opts.body !== undefined && !(opts.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  if (!opts.skipAuth) {
    const auth = useAuthStore();
    if (auth.token) headers["Authorization"] = `Bearer ${auth.token}`;
  }

  if (!opts.skipTenant) {
    const cnpj = opts.cnpj ?? useEmpresaStore().currentCnpj;
    if (cnpj) headers["X-Empresa-CNPJ"] = cnpj;
  }

  const init: RequestInit = {
    method: opts.method ?? "GET",
    headers,
  };
  if (opts.body !== undefined) {
    init.body =
      opts.body instanceof FormData ? opts.body : JSON.stringify(opts.body);
  }
  const res = await fetch(`${BASE}${path}`, init);

  let body: unknown = null;
  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/json")) {
    body = await res.json().catch(() => null);
  } else {
    body = await res.text().catch(() => null);
  }

  if (!res.ok) {
    if (res.status === 401 && !opts.skipAuth) {
      // Sessao invalida — limpa estado em memoria.
      // skipAuth=true (ex: /auth/login, health check) NAO deve deslogar:
      // 401 ali eh credencial errada / rota publica que tava protegida,
      // nao expirou nada do usuario.
      const auth = useAuthStore();
      auth.clear();
    }
    // FastAPI usa `detail`, Express usa `error`. Tenta os dois.
    let msg = `HTTP ${res.status}`;
    if (body && typeof body === "object") {
      const b = body as Record<string, unknown>;
      if (typeof b.detail === "string") msg = b.detail;
      else if (typeof b.error === "string") msg = b.error;
      else if (typeof b.message === "string") msg = b.message;
    } else if (typeof body === "string" && body.trim() && body.length < 300) {
      msg = body;
    }
    const err = new Error(msg) as ApiError;
    err.status = res.status;
    err.body = body;
    throw err;
  }

  return body as T;
}

export const api = {
  get: <T = unknown>(
    path: string,
    opts?: Omit<RequestOptions, "method" | "body">,
  ) => request<T>(path, { ...opts, method: "GET" }),
  post: <T = unknown>(
    path: string,
    body?: unknown,
    opts?: Omit<RequestOptions, "method">,
  ) => request<T>(path, { ...opts, method: "POST", body }),
  put: <T = unknown>(
    path: string,
    body?: unknown,
    opts?: Omit<RequestOptions, "method">,
  ) => request<T>(path, { ...opts, method: "PUT", body }),
  patch: <T = unknown>(
    path: string,
    body?: unknown,
    opts?: Omit<RequestOptions, "method">,
  ) => request<T>(path, { ...opts, method: "PATCH", body }),
  del: <T = unknown>(
    path: string,
    opts?: Omit<RequestOptions, "method" | "body">,
  ) => request<T>(path, { ...opts, method: "DELETE" }),
};
