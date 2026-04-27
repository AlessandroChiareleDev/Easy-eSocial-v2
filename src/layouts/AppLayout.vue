<script setup lang="ts">
import { computed } from "vue";
import { useRouter, RouterView } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { useApiHealth } from "@/composables/useApiHealth";
import AppBackground from "@/components/base/AppBackground.vue";

const auth = useAuthStore();
const router = useRouter();
const health = useApiHealth();

const userName = computed(
  () => auth.user?.nome || auth.user?.username || "convidado",
);

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
  router.replace("/login");
}
</script>

<template>
  <AppBackground />
  <div class="blush-aura" aria-hidden="true"></div>
  <div class="blush-aura blush-aura--secondary" aria-hidden="true"></div>

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
  inset: -25%;
  border-radius: inherit;
  background: radial-gradient(
    ellipse 38% 32% at 25% 25%,
    rgba(255, 255, 255, 1) 0%,
    rgba(255, 240, 248, 0.85) 25%,
    rgba(255, 220, 240, 0.4) 55%,
    transparent 75%
  );
  pointer-events: none;
  z-index: 1;
  animation:
    brand-orbit 9s linear infinite,
    brand-pulse 2.4s ease-in-out infinite;
}
@keyframes brand-orbit {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
@keyframes brand-pulse {
  0%,
  100% {
    opacity: 0.82;
  }
  50% {
    opacity: 1;
  }
}
@media (prefers-reduced-motion: reduce) {
  .brand-mark::before {
    animation: none;
  }
}
.brand-mark::after {
  content: "es";
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: 14px;
  color: #1a1a1a;
  letter-spacing: -0.04em;
  z-index: 2;
}
.brand-name {
  font-weight: 600;
  font-size: 16px;
}
.brand-tag {
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 9px;
  color: var(--secondary);
  background: rgba(61, 242, 75, 0.06);
  padding: 3px 8px;
  border-radius: 4px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  border: 1px solid rgba(61, 242, 75, 0.3);
  text-shadow: 0 0 6px rgba(61, 242, 75, 0.5);
}

.live-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px 5px 10px;
  background: rgba(61, 242, 75, 0.06);
  border: 1px solid rgba(61, 242, 75, 0.28);
  border-radius: 100px;
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 10.5px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--secondary);
  box-shadow:
    0 0 10px rgba(61, 242, 75, 0.18),
    inset 0 0 8px rgba(61, 242, 75, 0.06);
  text-shadow: 0 0 6px rgba(61, 242, 75, 0.5);
}
.live-pill::before {
  content: "";
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--secondary);
  box-shadow:
    0 0 8px var(--secondary),
    0 0 14px rgba(61, 242, 75, 0.7);
  animation: live-pulse 1.6s ease-in-out infinite;
}
@keyframes live-pulse {
  0%,
  100% {
    opacity: 1;
    box-shadow:
      0 0 8px var(--secondary),
      0 0 14px rgba(61, 242, 75, 0.7);
  }
  50% {
    opacity: 0.55;
    box-shadow:
      0 0 4px var(--secondary),
      0 0 6px rgba(61, 242, 75, 0.3);
  }
}

/* offline — vermelho suave, sem pulse */
.live-pill--offline {
  background: rgba(255, 90, 110, 0.06);
  border-color: rgba(255, 90, 110, 0.32);
  color: #ff8a9c;
  text-shadow: 0 0 6px rgba(255, 90, 110, 0.5);
  box-shadow:
    0 0 10px rgba(255, 90, 110, 0.18),
    inset 0 0 8px rgba(255, 90, 110, 0.06);
}
.live-pill--offline::before {
  background: #ff5a6e;
  box-shadow:
    0 0 8px #ff5a6e,
    0 0 14px rgba(255, 90, 110, 0.7);
  animation: none;
}

/* checking — Blush Frost, pulse mais lento */
.live-pill--checking,
.live-pill--idle {
  background: rgba(240, 209, 229, 0.05);
  border-color: rgba(240, 209, 229, 0.28);
  color: var(--primary);
  text-shadow: 0 0 6px rgba(240, 209, 229, 0.5);
  box-shadow:
    0 0 10px rgba(240, 209, 229, 0.14),
    inset 0 0 8px rgba(240, 209, 229, 0.05);
}
.live-pill--checking::before,
.live-pill--idle::before {
  background: var(--primary);
  box-shadow:
    0 0 8px var(--primary),
    0 0 14px rgba(240, 209, 229, 0.6);
  animation-duration: 2.4s;
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
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary), #c89bb8);
  display: grid;
  place-items: center;
  font-weight: 600;
  font-size: 11.5px;
  color: #1a1a1a;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.4);
}
.user-name {
  font-size: 13px;
  font-weight: 500;
  text-transform: lowercase;
}

.content {
  position: relative;
  z-index: 2;
}
</style>
