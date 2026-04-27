/**
 * Cliente HTTP pro backend Python (FastAPI :8000).
 * TUDO de eSocial S-1010/S-1210 mora aqui.
 *
 * Proxy via Vite: /py-api/* → http://localhost:8000/*
 */

const PY_BASE = "/py-api";

export interface PyApiError extends Error {
  status: number;
  body?: unknown;
}

interface PyOptions {
  query?: Record<string, string | number | boolean | undefined | null>;
  signal?: AbortSignal;
}

function buildQuery(q?: PyOptions["query"]): string {
  if (!q) return "";
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(q)) {
    if (v === undefined || v === null || v === "") continue;
    params.set(k, String(v));
  }
  const s = params.toString();
  return s ? `?${s}` : "";
}

async function pyGet<T = unknown>(
  path: string,
  opts: PyOptions = {},
): Promise<T> {
  const init: RequestInit = {
    method: "GET",
    headers: { Accept: "application/json" },
  };
  if (opts.signal) init.signal = opts.signal;
  const res = await fetch(`${PY_BASE}${path}${buildQuery(opts.query)}`, init);

  let body: unknown = null;
  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/json")) {
    body = await res.json().catch(() => null);
  } else {
    body = await res.text().catch(() => null);
  }

  if (!res.ok) {
    const err = new Error(
      typeof body === "object" && body && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : `HTTP ${res.status}`,
    ) as PyApiError;
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return body as T;
}

export const pyApi = { get: pyGet };
