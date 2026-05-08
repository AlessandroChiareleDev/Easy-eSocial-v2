<script setup lang="ts">
import { computed } from "vue";
import { useRouter, RouterView } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { useEmpresaStore } from "@/stores/empresa";
import { useApiHealth } from "@/composables/useApiHealth";
import AppBackground from "@/components/base/AppBackground.vue";

const auth = useAuthStore();
const empresa = useEmpresaStore();
const router = useRouter();
const health = useApiHealth();

const userName = computed(
  () => auth.user?.nome || auth.user?.email || "convidado",
);

const empresaLabel = computed(() => empresa.current?.razao_social ?? "—");

const healthLabel = computed(() => {
  switch (health.status.value) {
    case "online":
      return health.latencyMs.value !== null
        ? `backend · online · ${health.latencyMs.value}ms`
        : "backend · online";
    case "offline":
      return "backend · offline";
    case "checking":
      return "backend · verificando…";
    default:
      return "backend · —";
  }
});

function logout() {
  auth.clear();
  empresa.clear();
  router.replace("/login");
}

function trocarEmpresa() {
  empresa.clear();
  router.push("/empresas");
}
</script>

<template>
  <AppBackground />

  <div class="shell">
    <header class="topbar">
      <RouterLink to="/" class="brand">
        <div class="brand-mark"></div>
        <div class="brand-name">Easy-Social</div>
        <div class="brand-tag">v2 · cérebro</div>
      </RouterLink>

      <span
        class="live-pill"
        :class="`live-pill--${health.status.value}`"
        :title="
          health.lastCheckedAt.value
            ? `verificado ${health.lastCheckedAt.value.toLocaleTimeString('pt-BR')}`
            : ''
        "
      >
        {{ healthLabel }}
      </span>

      <button
        v-if="empresa.current"
        class="empresa-chip"
        type="button"
        @click="trocarEmpresa"
        :title="`empresa atual: ${empresaLabel} (clique pra trocar)`"
      >
        <span class="empresa-dot"></span>
        <span class="empresa-name">{{ empresaLabel }}</span>
        <span class="empresa-cta">trocar</span>
      </button>

      <div
        class="user-chip"
        @click="logout"
        role="button"
        :title="`sair (${userName})`"
      >
        <div class="avatar">{{ auth.initials }}</div>
        <div class="user-name">{{ userName }}</div>
      </div>
    </header>

    <main class="content">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.shell {
  position: relative;
  z-index: 2;
  min-height: 100vh;
  display: grid;
  grid-template-rows: auto 1fr;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 22px 40px;
  gap: 16px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  text-decoration: none;
  color: inherit;
}
.brand-mark {
  width: 36px;
  height: 36px;
  border-radius: 11px;
  position: relative;
  isolation: isolate;
  background:
    radial-gradient(
      ellipse at 90% 100%,
      rgba(61, 242, 75, 0.9) 0%,
      transparent 32%
    ),
    radial-gradient(
      ellipse 80% 70% at 65% 60%,
      rgba(200, 175, 235, 0.6) 0%,
      transparent 55%
    ),
    linear-gradient(135deg, #ffe4f0 0%, var(--primary) 55%, #c89bb8 100%);
  box-shadow:
    0 0 18px var(--primary-40),
    0 0 36px rgba(61, 242, 75, 0.18),
    inset 0 2px 1px rgba(255, 255, 255, 0.6),
    inset 0 -1px 1px rgba(180, 100, 150, 0.3);
  overflow: hidden;
}
.brand-mark::before {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: radial-gradient(
    ellipse 60% 50% at 30% 25%,
    rgba(255, 255, 255, 0.55) 0%,
    transparent 70%
  );
  pointer-events: none;
  z-index: 1;
}
.brand-mark::after {
  content: "es";
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: 15px;
  color: #1a1a1a;
  letter-spacing: -0.04em;
  z-index: 2;
}
.brand-name {
  font-weight: 600;
  font-size: 18px;
  letter-spacing: -0.01em;
}
.brand-tag {
  font-family: "JetBrains Mono", ui-monospace, monospace;
  font-size: 13px;
  color: var(--secondary);
  background: rgba(61, 242, 75, 0.06);
  padding: 3px 8px;
  border-radius: 4px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  border: 1px solid rgba(61, 242, 75, 0.22);
}

.live-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px 6px 12px;
  background: rgba(61, 242, 75, 0.05);
  border: 1px solid rgba(61, 242, 75, 0.22);
  border-radius: 100px;
  font-family: "JetBrains Mono", ui-monospace, monospace;
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--secondary);
}
.live-pill::before {
  content: "";
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--secondary);
  box-shadow: 0 0 6px rgba(61, 242, 75, 0.55);
  animation: live-pulse 2.4s ease-in-out infinite;
}
@keyframes live-pulse {
  0%,
  100% {
    opacity: 0.85;
  }
  50% {
    opacity: 0.45;
  }
}

/* offline — vermelho suave, sem pulse */
.live-pill--offline {
  background: rgba(255, 90, 110, 0.05);
  border-color: rgba(255, 90, 110, 0.25);
  color: #ff8a9c;
}
.live-pill--offline::before {
  background: #ff5a6e;
  box-shadow: 0 0 6px rgba(255, 90, 110, 0.55);
  animation: none;
}

/* checking — Blush Frost, pulse mais lento */
.live-pill--checking,
.live-pill--idle {
  background: rgba(240, 209, 229, 0.04);
  border-color: rgba(240, 209, 229, 0.22);
  color: var(--primary);
}
.live-pill--checking::before,
.live-pill--idle::before {
  background: var(--primary);
  box-shadow: 0 0 6px rgba(240, 209, 229, 0.5);
  animation-duration: 3s;
}

.empresa-chip {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 6px 14px;
  margin-left: auto;
  background: var(--glass-bg);
  backdrop-filter: blur(12px);
  border: var(--glass-border);
  border-radius: 100px;
  cursor: pointer;
  color: inherit;
  font: inherit;
  font-size: 0.85rem;
  transition: border-color 0.15s ease;
}
.empresa-chip:hover {
  border-color: rgba(96, 165, 250, 0.5);
}
.empresa-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #60a5fa;
  box-shadow: 0 0 8px rgba(96, 165, 250, 0.6);
}
.empresa-name {
  font-weight: 600;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.empresa-cta {
  color: #94a3b8;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 14px 6px 6px;
  background: var(--glass-bg);
  backdrop-filter: blur(12px);
  border: var(--glass-border);
  border-radius: 100px;
  cursor: pointer;
  transition: border-color var(--duration-base) var(--ease-glass);
}
.user-chip:hover {
  border-color: rgba(240, 209, 229, 0.35);
}
.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary), #c89bb8);
  display: grid;
  place-items: center;
  font-weight: 600;
  font-size: 14px;
  color: #1a1a1a;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.4);
}
.user-name {
  font-size: 15px;
  font-weight: 500;
  text-transform: lowercase;
}

.content {
  position: relative;
  z-index: 2;
}
</style>
