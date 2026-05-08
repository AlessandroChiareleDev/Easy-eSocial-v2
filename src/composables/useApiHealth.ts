/**
 * Health check do backend Express :3333 — chamado via proxy /api/health
 *
 * Retorna estado reativo: 'online' | 'offline' | 'checking' | 'idle'
 * Faz polling automático no intervalo informado (default 20s) enquanto
 * houver consumer mounted.
 */

import { ref, onMounted, onBeforeUnmount } from "vue";
import { api } from "@/services/api";

export type HealthStatus = "idle" | "checking" | "online" | "offline";

interface HealthOptions {
  /** ms entre pings; default 20s */
  interval?: number;
  /** se true, não auto-roda */
  manual?: boolean;
}

export function useApiHealth(opts: HealthOptions = {}) {
  const interval = opts.interval ?? 20_000;
  const status = ref<HealthStatus>("idle");
  const lastCheckedAt = ref<Date | null>(null);
  const latencyMs = ref<number | null>(null);

  let timer: number | null = null;

  async function check() {
    status.value = "checking";
    const t0 = performance.now();
    try {
      // Ping direto via fetch: se o servidor RESPONDE com qualquer
      // status HTTP (ate 401/404), o backend esta vivo. So consideramos
      // offline em erro de rede / timeout / 5xx.
      const ctrl = new AbortController();
      const to = window.setTimeout(() => ctrl.abort(), 8_000);
      const res = await fetch("/api/health", {
        method: "GET",
        signal: ctrl.signal,
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      window.clearTimeout(to);
      latencyMs.value = Math.round(performance.now() - t0);
      // 5xx = backend reclamando, marca offline. 2xx/3xx/4xx = vivo.
      status.value = res.status >= 500 ? "offline" : "online";
    } catch {
      latencyMs.value = null;
      status.value = "offline";
    } finally {
      lastCheckedAt.value = new Date();
    }
  }

  function start() {
    if (timer !== null) return;
    void check();
    timer = window.setInterval(check, interval);
  }

  function stop() {
    if (timer !== null) {
      clearInterval(timer);
      timer = null;
    }
  }

  if (!opts.manual) {
    onMounted(start);
    onBeforeUnmount(stop);
  }

  return { status, lastCheckedAt, latencyMs, check, start, stop };
}
