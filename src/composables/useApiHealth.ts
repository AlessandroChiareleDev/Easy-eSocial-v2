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
      // /health é público no backend antigo
      await api.get("/health", { skipAuth: true });
      latencyMs.value = Math.round(performance.now() - t0);
      status.value = "online";
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
