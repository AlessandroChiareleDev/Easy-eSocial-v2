<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { useStats } from "@/composables/useStats";
import BrainStage from "@/components/base/BrainStage.vue";

const auth = useAuthStore();
const { stats } = useStats();

const greetingName = computed(
  () => auth.user?.nome || auth.user?.username || "operador",
);

const today = new Date();
const dateLabel = today.toLocaleDateString("pt-BR", {
  day: "numeric",
  month: "long",
  year: "numeric",
});
const hour = today.getHours();
const greeting =
  hour < 6
    ? "Boa madrugada"
    : hour < 12
      ? "Bom dia"
      : hour < 18
        ? "Boa tarde"
        : "Boa noite";

function fmtNum(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString("pt-BR");
}
function fmtPct(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return `${n.toFixed(2)}%`;
}

interface Card {
  to: string;
  title: string;
  desc: string;
  num: string;
  numLabel: string;
  isPct?: boolean;
  glow?: boolean;
  icon: "grid" | "send" | "calendar" | "logs";
}

const cards = computed<Card[]>(() => [
  {
    to: "/tabelas",
    title: "Tabelas",
    desc: "S-1000 · S-1005 · S-1010 · rubricas · lotações",
    num: fmtNum(stats.value.totalTabelas),
    numLabel: "tabelas",
    icon: "grid",
  },
  {
    to: "/esocial/s1010",
    title: "eSocial S-1010",
    desc: "rubricas · webservice · envio",
    num: fmtNum(stats.value.totalLotes),
    numLabel: "lotes",
    icon: "send",
  },
  {
    to: "/esocial/s1210-anual",
    title: "S-1210 Anual",
    desc: "eventos anuais · validação",
    num: fmtPct(stats.value.pctOk),
    numLabel: "ok",
    isPct: true,
    glow: true,
    icon: "calendar",
  },
  {
    to: "/logs",
    title: "Logs de Sistema",
    desc: "auditoria · histórico · respostas eSocial",
    num: fmtNum(stats.value.totalLogs),
    numLabel: "eventos",
    icon: "logs",
  },
]);

const branchPaths = [
  { d: "M 440,0 L 440,42 C 440,80 200,75 130,108", dur: "2.4s" },
  { d: "M 440,0 L 440,42 C 440,80 360,80 350,108", dur: "2.0s" },
  { d: "M 440,0 L 440,42 C 440,80 520,80 530,108", dur: "2.2s" },
  { d: "M 440,0 L 440,42 C 440,80 680,75 750,108", dur: "2.6s" },
];
</script>

<template>
  <main class="page">
    <header class="greeting">
      <div class="crumb">Cérebro Operacional · APPA · 2026</div>
      <h1>
        {{ greeting }}, <span class="name-grad">{{ greetingName }}</span>
      </h1>
      <p class="sub">{{ dateLabel }} · sincronizado há 2 min</p>
    </header>

    <section class="brain-wrap">
      <BrainStage />
      <div class="float-metric m1">
        <span class="num">{{ fmtNum(stats.totalCpfs) }}</span> CPFs
      </div>
      <div class="float-metric m2">
        <span class="num">{{ fmtPct(stats.pctOk) }}</span> ok
      </div>
      <div class="float-metric m3">
        S-1210 · <span class="num">{{ stats.ultimoPeriodo ?? "—" }}</span>
      </div>
      <div class="float-metric m4">
        <span class="num">{{ fmtNum(stats.pendentes) }}</span> pendentes
      </div>
    </section>

    <section class="branch">
      <svg
        class="branch-svg"
        viewBox="0 0 880 110"
        fill="none"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="wireGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#3df24b" stop-opacity="0.9" />
            <stop offset="100%" stop-color="#3df24b" stop-opacity="0.25" />
          </linearGradient>
          <filter id="wireGlow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <path
          d="M 440,0 L 440,40"
          stroke="url(#wireGrad)"
          stroke-width="2.5"
          filter="url(#wireGlow)"
        />
        <circle cx="440" cy="42" r="4" fill="#d4ffd9" filter="url(#wireGlow)" />
        <circle
          cx="440"
          cy="42"
          r="9"
          stroke="#3df24b"
          stroke-width="0.8"
          opacity="0.5"
          fill="none"
        />

        <path
          v-for="p in branchPaths"
          :key="p.d"
          :d="p.d"
          stroke="url(#wireGrad)"
          stroke-width="1.5"
          fill="none"
          filter="url(#wireGlow)"
          opacity="0.88"
        />

        <template v-for="p in branchPaths" :key="`p-${p.d}`">
          <circle r="3" class="particle" fill="#ffffff" filter="url(#wireGlow)">
            <animateMotion :dur="p.dur" repeatCount="indefinite" :path="p.d" />
          </circle>
          <circle
            r="2.4"
            class="particle"
            fill="#9ff7a6"
            filter="url(#wireGlow)"
          >
            <animateMotion
              :dur="p.dur"
              begin="0.8s"
              repeatCount="indefinite"
              :path="p.d"
            />
          </circle>
          <circle
            r="2"
            class="particle"
            fill="#3df24b"
            filter="url(#wireGlow)"
            opacity="0.8"
          >
            <animateMotion
              :dur="p.dur"
              begin="1.6s"
              repeatCount="indefinite"
              :path="p.d"
            />
          </circle>
        </template>
      </svg>

      <div class="options">
        <RouterLink
          v-for="c in cards"
          :key="c.to"
          :to="c.to"
          class="opt-card"
          :class="{ 'opt-card--glow': c.glow }"
        >
          <div class="opt-icon">
            <svg
              v-if="c.icon === 'grid'"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <rect x="3" y="3" width="7" height="7" rx="1.5" />
              <rect x="14" y="3" width="7" height="7" rx="1.5" />
              <rect x="3" y="14" width="7" height="7" rx="1.5" />
              <rect x="14" y="14" width="7" height="7" rx="1.5" />
            </svg>
            <svg
              v-else-if="c.icon === 'send'"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M22 2 11 13" />
              <path d="M22 2 15 22l-4-9-9-4z" />
            </svg>
            <svg
              v-else-if="c.icon === 'calendar'"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <rect x="3" y="4" width="18" height="18" rx="2" />
              <path d="M16 2v4M8 2v4M3 10h18" />
            </svg>
            <svg
              v-else
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path
                d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
              />
              <path d="M14 2v6h6M9 13h6M9 17h6M9 9h2" />
            </svg>
          </div>

          <div class="opt-title">{{ c.title }}</div>
          <div class="opt-desc">{{ c.desc }}</div>

          <div class="opt-arrow">
            <svg
              width="11"
              height="11"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2.5"
              stroke-linecap="round"
            >
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </div>

          <div class="opt-meta">
            <div>
              <div class="opt-meta-num" :class="{ 'is-pct': c.isPct }">
                {{ c.num }}
              </div>
              <div class="opt-meta-label">{{ c.numLabel }}</div>
            </div>
          </div>
        </RouterLink>
      </div>

      <RouterLink to="/problemas" class="alert-card liquid-glass">
        <div class="alert-icon">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="1.7"
          >
            <path d="M12 9v4M12 17h.01" />
            <path
              d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"
            />
          </svg>
        </div>
        <div class="alert-body">
          <div class="alert-title">Problemas</div>
          <div class="alert-desc">erros L1 / L2 · pendências · reenvios</div>
        </div>
        <div class="alert-num">
          <span class="num gg-glow">{{ fmtNum(stats.pendentes) }}</span>
          abertos
        </div>
      </RouterLink>

      <footer class="footer">
        <span class="dot">●</span> Easy-Social v2 · backend express:3333 ·
        postgres supabase
      </footer>
    </section>
  </main>
</template>

<style scoped>
.page {
  max-width: 1180px;
  margin: 0 auto;
  padding: 12px 32px 64px;
}

.greeting {
  text-align: center;
  margin-bottom: 8px;
}
.crumb {
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 13px;
  color: var(--text-muted);
  letter-spacing: 0.18em;
  text-transform: uppercase;
  margin-bottom: 8px;
}
.greeting h1 {
  font-size: 26px;
  font-weight: 500;
  letter-spacing: -0.02em;
  margin: 0;
}
.name-grad {
  color: var(--primary);
}
.sub {
  margin-top: 4px;
  font-size: 14px;
  color: var(--text-muted);
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  letter-spacing: 0.04em;
}

.brain-wrap {
  position: relative;
  display: grid;
  place-items: center;
  margin: 18px auto 12px;
  width: 360px;
  height: 280px;
}
.float-metric {
  position: absolute;
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 13px;
  color: rgba(61, 242, 75, 0.85);
  text-shadow: 0 0 6px rgba(61, 242, 75, 0.4);
  background: rgba(11, 14, 20, 0.6);
  backdrop-filter: blur(8px);
  padding: 5px 10px;
  border-radius: 100px;
  border: 1px solid rgba(61, 242, 75, 0.22);
  box-shadow: 0 0 12px rgba(61, 242, 75, 0.18);
  white-space: nowrap;
  letter-spacing: 0.06em;
  z-index: 3;
}
.float-metric .num {
  color: #fff;
  font-weight: 600;
  text-shadow: 0 0 8px rgba(61, 242, 75, 0.5);
}
.float-metric.m1 {
  top: 10px;
  left: -4px;
}
.float-metric.m2 {
  top: 30px;
  right: -10px;
}
.float-metric.m3 {
  bottom: 60px;
  left: -28px;
}
.float-metric.m4 {
  bottom: 76px;
  right: -22px;
}

.branch {
  position: relative;
  width: 100%;
  max-width: 1100px;
  margin: 0 auto;
}
.branch-svg {
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  width: 880px;
  height: 110px;
  pointer-events: none;
  overflow: visible;
}
.particle {
  filter: drop-shadow(0 0 4px var(--secondary))
    drop-shadow(0 0 8px rgba(61, 242, 75, 0.6));
}

.options {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 18px;
  max-width: 1100px;
  margin: 12px auto 0;
}
@media (max-width: 900px) {
  .options {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 540px) {
  .options {
    grid-template-columns: 1fr;
  }
}

.opt-card {
  position: relative;
  display: block;
  text-decoration: none;
  color: inherit;
  padding: 22px 22px 20px;
  background: var(--glass-bg);
  backdrop-filter: blur(20px) saturate(140%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-lg);
  box-shadow: var(--glass-shadow), var(--glass-inner-highlight);
  transition: all 280ms var(--ease-glass);
  cursor: pointer;
  overflow: hidden;
}
.opt-card::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(61, 242, 75, 0.5),
    transparent
  );
}
.opt-card::after {
  content: "";
  position: absolute;
  inset: -1px;
  border-radius: inherit;
  padding: 1px;
  background: linear-gradient(
    135deg,
    rgba(61, 242, 75, 0.4),
    transparent 40%,
    transparent 60%,
    rgba(240, 209, 229, 0.25)
  );
  -webkit-mask:
    linear-gradient(#000 0 0) content-box,
    linear-gradient(#000 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  opacity: 0.7;
  pointer-events: none;
}
.opt-card:hover {
  transform: translateY(-3px);
  border-color: rgba(61, 242, 75, 0.4);
  box-shadow:
    0 12px 36px rgba(0, 0, 0, 0.5),
    0 0 0 1px rgba(61, 242, 75, 0.3),
    0 0 32px rgba(61, 242, 75, 0.25),
    var(--glass-inner-highlight);
}

.opt-icon {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: rgba(61, 242, 75, 0.06);
  border: 1px solid rgba(61, 242, 75, 0.25);
  display: grid;
  place-items: center;
  color: var(--secondary);
  margin-bottom: 14px;
  box-shadow:
    0 0 12px rgba(61, 242, 75, 0.2),
    inset 0 0 8px rgba(61, 242, 75, 0.08);
  position: relative;
}
.opt-icon svg {
  width: 18px;
  height: 18px;
  stroke-width: 1.7;
  filter: drop-shadow(0 0 4px rgba(61, 242, 75, 0.6));
}
.opt-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 4px;
  letter-spacing: -0.01em;
}
.opt-desc {
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.5;
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  letter-spacing: 0.02em;
}

.opt-arrow {
  position: absolute;
  top: 22px;
  right: 22px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: rgba(61, 242, 75, 0.08);
  border: 1px solid rgba(61, 242, 75, 0.25);
  display: grid;
  place-items: center;
  color: var(--secondary);
  transition: all 240ms var(--ease-glass);
}
.opt-card:hover .opt-arrow {
  background: rgba(61, 242, 75, 0.18);
  border-color: rgba(61, 242, 75, 0.6);
  transform: rotate(-45deg) translateX(2px);
  box-shadow: 0 0 14px rgba(61, 242, 75, 0.5);
}

.opt-meta {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.opt-meta-num {
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  text-shadow: 0 0 8px rgba(61, 242, 75, 0.4);
  letter-spacing: -0.02em;
}
.opt-meta-label {
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 13px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.opt-card--glow {
  background:
    radial-gradient(
      120% 80% at 0% 0%,
      rgba(61, 242, 75, 0.1) 0%,
      transparent 55%
    ),
    rgba(11, 14, 20, 0.55);
  border-color: rgba(255, 255, 255, 0.06);
  box-shadow:
    0 12px 40px rgba(0, 0, 0, 0.55),
    inset 0 1px 0 rgba(240, 209, 229, 0.18),
    inset 0 -1px 0 rgba(61, 242, 75, 0.08);
}
.opt-card--glow::before {
  background: linear-gradient(
    90deg,
    transparent,
    rgba(240, 209, 229, 0.65),
    rgba(61, 242, 75, 0.35),
    transparent
  );
}
.opt-card--glow .opt-icon::before {
  content: "";
  position: absolute;
  left: -40px;
  top: -30px;
  width: 180px;
  height: 180px;
  border-radius: 50%;
  background: radial-gradient(
    circle,
    rgba(61, 242, 75, 0.28) 0%,
    rgba(61, 242, 75, 0.1) 35%,
    transparent 70%
  );
  filter: blur(22px);
  pointer-events: none;
  z-index: -1;
}
.opt-card--glow .opt-meta-num.is-pct {
  font-size: 14px;
  text-shadow:
    0 0 4px rgba(255, 255, 255, 0.85),
    0 0 10px rgba(61, 242, 75, 0.85),
    0 0 22px rgba(61, 242, 75, 0.45);
  opacity: 0.95;
}
.opt-card--glow .opt-arrow {
  background: rgba(240, 209, 229, 0.06);
  border-color: rgba(240, 209, 229, 0.25);
  color: var(--primary);
  box-shadow:
    0 0 16px rgba(240, 209, 229, 0.18),
    inset 0 0 6px rgba(240, 209, 229, 0.08);
}

.alert-card {
  margin-top: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 22px;
  text-decoration: none;
  color: inherit;
  transition: all 240ms var(--ease-glass);
}
.alert-card:hover {
  border-color: rgba(255, 180, 80, 0.35);
  box-shadow:
    0 12px 36px rgba(0, 0, 0, 0.5),
    0 0 0 1px rgba(255, 180, 80, 0.25),
    0 0 28px rgba(255, 180, 80, 0.12);
}
.alert-icon {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: rgba(255, 180, 80, 0.08);
  border: 1px solid rgba(255, 180, 80, 0.3);
  display: grid;
  place-items: center;
  color: #ffc36e;
  box-shadow: 0 0 12px rgba(255, 180, 80, 0.18);
  flex-shrink: 0;
}
.alert-icon svg {
  width: 18px;
  height: 18px;
}
.alert-body {
  flex: 1;
}
.alert-title {
  font-weight: 600;
  font-size: 15px;
}
.alert-desc {
  margin-top: 2px;
  font-size: 13px;
  color: var(--text-muted);
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
}
.alert-num {
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 13px;
  color: var(--text-muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.alert-num .num {
  font-size: 16px;
  margin-right: 4px;
}

.footer {
  text-align: center;
  font-family: "JetBrains Mono Variable", ui-monospace, monospace;
  font-size: 13px;
  color: var(--text-muted);
  letter-spacing: 0.08em;
  margin-top: 28px;
}
.footer .dot {
  color: var(--secondary);
}
</style>
