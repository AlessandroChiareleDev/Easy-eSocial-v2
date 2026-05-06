<script setup lang="ts">
/**
 * Fundo global — versão refinada
 * Sem rotação, sem grid, sem meteoros. Apenas dois orbes estáticos
 * muito difusos + vinheta. Calmo e elegante.
 */
</script>

<template>
  <div class="bg-canvas" aria-hidden="true">
    <div class="orb orb--blush"></div>
    <div class="orb orb--ghost"></div>
    <div class="vignette"></div>
  </div>
</template>

<style scoped>
.bg-canvas {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
  background:
    radial-gradient(
      ellipse 120% 80% at 50% 0%,
      #11151f 0%,
      #0b0e14 55%,
      #07090f 100%
    );
}

.orb {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
  filter: blur(110px);
  opacity: 0.55;
}
.orb--blush {
  top: -18vmin;
  left: -14vmin;
  width: 70vmin;
  height: 70vmin;
  background: radial-gradient(
    circle at 50% 50%,
    rgba(240, 209, 229, 0.32) 0%,
    rgba(200, 175, 235, 0.16) 45%,
    transparent 75%
  );
}
.orb--ghost {
  bottom: -22vmin;
  right: -18vmin;
  width: 75vmin;
  height: 75vmin;
  background: radial-gradient(
    circle at 50% 50%,
    rgba(61, 242, 75, 0.16) 0%,
    rgba(61, 242, 75, 0.07) 45%,
    transparent 75%
  );
}

.vignette {
  position: absolute;
  inset: 0;
  background: radial-gradient(
    ellipse 100% 80% at 50% 50%,
    transparent 50%,
    rgba(0, 0, 0, 0.4) 100%
  );
}
</style>
