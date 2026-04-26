<script setup lang="ts">
import brainFull from '@/assets/brain/brain-full.png';
</script>

<template>
  <div class="brain-stage">
    <div class="ring r1" aria-hidden="true"></div>
    <div class="ring r2" aria-hidden="true"></div>
    <div class="ring r3" aria-hidden="true"></div>
    <img class="brain-img" :src="brainFull" alt="Cérebro Operacional" />
  </div>
</template>

<style scoped>
.brain-stage {
  position: relative;
  width: 360px;
  height: 280px;
  display: grid;
  place-items: center;
}

/* Aura "luz traseira" — núcleo quase branco, bordas neon, some */
.brain-stage::before {
  content: '';
  position: absolute;
  inset: -90px;
  background: radial-gradient(
    circle at 50% 50%,
    rgba(220, 255, 226, 0.55) 0%,
    rgba(61, 242, 75, 0.32) 14%,
    rgba(61, 242, 75, 0.12) 36%,
    transparent 62%
  );
  filter: blur(30px);
  animation: brain-aura 4.2s ease-in-out infinite;
  pointer-events: none;
  z-index: 0;
}

/* Toque Blush Frost lateral — luz contrária */
.brain-stage::after {
  content: '';
  position: absolute;
  top: 40%;
  left: -10%;
  width: 220px;
  height: 220px;
  border-radius: 50%;
  background: radial-gradient(
    circle,
    rgba(240, 209, 229, 0.32) 0%,
    rgba(240, 209, 229, 0.08) 40%,
    transparent 70%
  );
  filter: blur(36px);
  pointer-events: none;
  z-index: 0;
}

@keyframes brain-aura {
  0%,
  100% {
    opacity: 0.75;
    transform: scale(1);
  }
  50% {
    opacity: 1;
    transform: scale(1.08);
  }
}

/* Cérebro fantasma — translúcido, mix-blend screen, luz vem de trás */
.brain-img {
  position: relative;
  z-index: 1;
  width: 320px;
  height: auto;
  display: block;
  user-select: none;
  filter: hue-rotate(-120deg) saturate(0.6) brightness(0.85) contrast(1.05)
    drop-shadow(0 0 18px rgba(61, 242, 75, 0.45))
    drop-shadow(0 0 48px rgba(61, 242, 75, 0.18));
  opacity: 0.32;
  mix-blend-mode: screen;
  animation: brain-breathe 4s ease-in-out infinite;
}

@keyframes brain-breathe {
  0%,
  100% {
    transform: scale(1);
    opacity: 0.3;
  }
  50% {
    transform: scale(1.025);
    opacity: 0.42;
  }
}

/* Anéis pulsantes */
.ring {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 240px;
  height: 200px;
  border-radius: 50%;
  border: 1px solid rgba(61, 242, 75, 0.55);
  transform: translate(-50%, -50%) scale(1);
  opacity: 0;
  pointer-events: none;
}
.r1 {
  animation: ring-pulse 3.4s ease-out infinite;
}
.r2 {
  animation: ring-pulse 3.4s ease-out infinite 1.1s;
}
.r3 {
  animation: ring-pulse 3.4s ease-out infinite 2.2s;
}

@keyframes ring-pulse {
  0% {
    opacity: 0.7;
    transform: translate(-50%, -50%) scale(0.6);
  }
  70% {
    opacity: 0.05;
  }
  100% {
    opacity: 0;
    transform: translate(-50%, -50%) scale(1.6);
  }
}
</style>
