<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  /** percentual 0..100 */
  percent: number;
  /** taxa atual em bytes/seg (para label opcional) */
  rate?: number;
  /** label central (ex: "42%" ou "subindo") */
  label?: string;
  /** sublabel (ex: "12,4 MB/s") */
  sublabel?: string;
  /** tamanho em px (default 220) */
  size?: number;
}>();

const size = computed(() => props.size ?? 220);
const stroke = computed(() => Math.max(8, size.value * 0.06));
const radius = computed(() => (size.value - stroke.value) / 2 - 4);
const cx = computed(() => size.value / 2);
const cy = computed(() => size.value / 2);

// arco de 240º (de -210º a +30º = 240º total)
const ARC_DEG = 240;
const START_DEG = -210; // grau inicial (canto inf-esq)

const polar = (deg: number) => {
  const rad = (deg * Math.PI) / 180;
  return {
    x: cx.value + radius.value * Math.cos(rad),
    y: cy.value + radius.value * Math.sin(rad),
  };
};

const arcPath = computed(() => {
  const start = polar(START_DEG);
  const end = polar(START_DEG + ARC_DEG);
  const largeArc = ARC_DEG > 180 ? 1 : 0;
  return `M ${start.x} ${start.y} A ${radius.value} ${radius.value} 0 ${largeArc} 1 ${end.x} ${end.y}`;
});

const arcLength = computed(() => (Math.PI * radius.value * ARC_DEG) / 180);

const dashOffset = computed(() => {
  const p = Math.max(0, Math.min(100, props.percent)) / 100;
  return arcLength.value * (1 - p);
});

const needleAngle = computed(() => {
  const p = Math.max(0, Math.min(100, props.percent)) / 100;
  return START_DEG + ARC_DEG * p;
});

const ticks = computed(() => {
  const out: {
    x1: number;
    y1: number;
    x2: number;
    y2: number;
    major: boolean;
  }[] = [];
  for (let i = 0; i <= 12; i++) {
    const major = i % 3 === 0;
    const deg = START_DEG + (ARC_DEG * i) / 12;
    const rad = (deg * Math.PI) / 180;
    const r1 = radius.value + 2;
    const r2 = radius.value + (major ? -10 : -6);
    out.push({
      x1: cx.value + r1 * Math.cos(rad),
      y1: cy.value + r1 * Math.sin(rad),
      x2: cx.value + r2 * Math.cos(rad),
      y2: cy.value + r2 * Math.sin(rad),
      major,
    });
  }
  return out;
});

const needleEnd = computed(() => {
  const rad = (needleAngle.value * Math.PI) / 180;
  return {
    x: cx.value + (radius.value - 14) * Math.cos(rad),
    y: cy.value + (radius.value - 14) * Math.sin(rad),
  };
});
</script>

<template>
  <div class="speedo" :style="{ width: size + 'px', height: size + 'px' }">
    <svg :width="size" :height="size" :viewBox="`0 0 ${size} ${size}`">
      <defs>
        <linearGradient :id="`grad-arc-${size}`" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stop-color="#3df24b" stop-opacity="0.85" />
          <stop offset="60%" stop-color="#9ff7a6" stop-opacity="0.95" />
          <stop offset="100%" stop-color="#ffffff" stop-opacity="1" />
        </linearGradient>
        <filter
          :id="`glow-${size}`"
          x="-30%"
          y="-30%"
          width="160%"
          height="160%"
        >
          <feGaussianBlur stdDeviation="3" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <!-- arco trilho -->
      <path
        :d="arcPath"
        :stroke-width="stroke"
        stroke="rgba(255,255,255,0.06)"
        fill="none"
        stroke-linecap="round"
      />

      <!-- ticks -->
      <line
        v-for="(t, i) in ticks"
        :key="i"
        :x1="t.x1"
        :y1="t.y1"
        :x2="t.x2"
        :y2="t.y2"
        :stroke="t.major ? 'rgba(240,209,229,0.55)' : 'rgba(240,209,229,0.22)'"
        :stroke-width="t.major ? 1.5 : 1"
      />

      <!-- arco progresso -->
      <path
        :d="arcPath"
        :stroke-width="stroke"
        :stroke="`url(#grad-arc-${size})`"
        fill="none"
        stroke-linecap="round"
        :stroke-dasharray="arcLength"
        :stroke-dashoffset="dashOffset"
        :filter="`url(#glow-${size})`"
        style="transition: stroke-dashoffset 120ms linear"
      />

      <!-- agulha -->
      <line
        :x1="cx"
        :y1="cy"
        :x2="needleEnd.x"
        :y2="needleEnd.y"
        stroke="#d4ffd9"
        stroke-width="2.4"
        stroke-linecap="round"
        :filter="`url(#glow-${size})`"
        style="transition: all 120ms ease-out"
      />
      <circle
        :cx="cx"
        :cy="cy"
        r="6"
        fill="#3df24b"
        :filter="`url(#glow-${size})`"
      />
      <circle :cx="cx" :cy="cy" r="2.5" fill="#ffffff" />
    </svg>

    <div class="speedo-text">
      <div class="big">{{ label ?? `${percent.toFixed(0)}%` }}</div>
      <div v-if="sublabel" class="sub">{{ sublabel }}</div>
    </div>
  </div>
</template>

<style scoped>
.speedo {
  position: relative;
  display: inline-block;
}
.speedo-text {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  padding-top: 10%;
}
.big {
  font-size: 2.2rem;
  font-weight: 700;
  color: #ffffff;
  text-shadow: 0 0 8px rgba(61, 242, 75, 0.45);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
}
.sub {
  font-size: 0.85rem;
  color: rgba(240, 209, 229, 0.75);
  margin-top: 4px;
  font-variant-numeric: tabular-nums;
}
</style>
