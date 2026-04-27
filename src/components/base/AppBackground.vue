<script setup lang="ts">
/**
 * Fundo global Liquid Glass / Ghost Green
 * - Camada iridescente (radiais Blush Frost + Ghost Green)
 * - Cônica difusa (mix-blend screen)
 * - Grid mascarado
 * - Meteoros caindo
 * - Auras Blush (já vivem no main.css)
 */
</script>

<template>
  <div class="bg-canvas" aria-hidden="true"></div>
  <div class="aura-orbit" aria-hidden="true">
    <div class="aura aura-blush"></div>
    <div class="aura aura-ghost"></div>
  </div>
  <div class="bg-grid" aria-hidden="true"></div>
  <div class="meteor" aria-hidden="true"></div>
  <div class="meteor" aria-hidden="true"></div>
  <div class="meteor" aria-hidden="true"></div>
  <div class="meteor" aria-hidden="true"></div>
</template>

<style scoped>
.bg-canvas {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
  background: var(--bg);
}
.bg-canvas::before {
  content: "";
  position: absolute;
  top: -15%;
  left: -15%;
  width: 60%;
  height: 65%;
  background: conic-gradient(
    from 210deg at 35% 40%,
    rgba(255, 200, 230, 0) 0deg,
    rgba(255, 220, 240, 0.18) 60deg,
    rgba(200, 180, 240, 0.22) 130deg,
    rgba(180, 220, 245, 0.18) 200deg,
    rgba(255, 240, 245, 0.15) 280deg,
    rgba(255, 200, 230, 0) 360deg
  );
  filter: blur(60px);
  mix-blend-mode: screen;
  pointer-events: none;
}

/* ============================================================
   Auras orbitando em sincronia, sempre 180° opostas.
   - .aura-orbit roda; ambas as auras estão dentro dela
   - Cada uma fica deslocada do centro em direções opostas
   ============================================================ */
.aura-orbit {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
  animation: aura-spin 60s linear infinite;
}
.aura {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 70vmin;
  height: 70vmin;
  border-radius: 50%;
  pointer-events: none;
  filter: blur(40px);
}
.aura-blush {
  background: radial-gradient(
    circle at 50% 50%,
    rgba(255, 255, 255, 0.45) 0%,
    rgba(240, 209, 229, 0.4) 25%,
    rgba(200, 175, 235, 0.25) 55%,
    transparent 75%
  );
  transform: translate(-50%, -50%) translate(-55vmin, -38vmin);
  animation: aura-pulse 6s ease-in-out infinite;
}
.aura-ghost {
  background: radial-gradient(
    circle at 50% 50%,
    rgba(61, 242, 75, 0.28) 0%,
    rgba(61, 242, 75, 0.16) 35%,
    transparent 70%
  );
  transform: translate(-50%, -50%) translate(55vmin, 38vmin);
  animation: aura-pulse 6s ease-in-out infinite;
  animation-delay: -3s;
}
@keyframes aura-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
@keyframes aura-pulse {
  0%,
  100% {
    opacity: 0.85;
  }
  50% {
    opacity: 1;
  }
}
@media (prefers-reduced-motion: reduce) {
  .aura-orbit {
    animation: none;
  }
  .aura {
    animation: none;
  }
}

.bg-grid {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.025) 1px, transparent 1px);
  background-size: 64px 64px;
  -webkit-mask-image: radial-gradient(
    ellipse 70% 70% at 50% 50%,
    black 0%,
    transparent 90%
  );
  mask-image: radial-gradient(
    ellipse 70% 70% at 50% 50%,
    black 0%,
    transparent 90%
  );
}

.meteor {
  position: fixed;
  top: -10%;
  width: 1px;
  height: 80px;
  pointer-events: none;
  z-index: 0;
  background: linear-gradient(
    180deg,
    transparent,
    rgba(61, 242, 75, 0.6),
    transparent
  );
  filter: blur(0.5px);
  animation: meteor 8s linear infinite;
  opacity: 0.4;
}
.meteor:nth-of-type(1) {
  left: 8%;
  animation-delay: 0s;
}
.meteor:nth-of-type(2) {
  left: 18%;
  animation-delay: 1s;
}
.meteor:nth-of-type(3) {
  left: 64%;
  animation-delay: 3.5s;
  animation-duration: 11s;
}
.meteor:nth-of-type(4) {
  left: 88%;
  animation-delay: 5.5s;
  animation-duration: 9s;
}
@keyframes meteor {
  0% {
    transform: translateY(-100px) translateX(0);
    opacity: 0;
  }
  10% {
    opacity: 0.5;
  }
  100% {
    transform: translateY(110vh) translateX(-200px);
    opacity: 0;
  }
}
</style>
