<script setup lang="ts">
import brainFull from "@/assets/brain/brain-full.png";
</script>

<template>
  <div class="brain-stage">
    <div class="ring r1" aria-hidden="true"></div>
    <div class="ring r2" aria-hidden="true"></div>
    <div class="ring r3" aria-hidden="true"></div>
    <img class="brain-img" :src="brainFull" alt="Cérebro Operacional" />

    <!-- Bolinhas verdes percorrendo SOMENTE os sulcos reais já desenhados na imagem.
         viewBox = dimensões nativas do PNG (1536x1024) e o SVG é posicionado/dimensionado
         exatamente igual ao <img>, então as coordenadas são pixels da imagem. -->
    <svg
      class="brain-trails"
      viewBox="0 0 1536 1024"
      preserveAspectRatio="xMidYMid meet"
      aria-hidden="true"
    >
      <defs>
        <radialGradient id="bt-dot" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="#ffffff" stop-opacity="1" />
          <stop offset="35%" stop-color="#3df24b" stop-opacity="1" />
          <stop offset="100%" stop-color="#3df24b" stop-opacity="0" />
        </radialGradient>

        <!-- Fissura central (vertical, divide os hemisférios) -->
        <path
          id="bt-pCenter"
          d="M 770 175 C 768 350, 770 520, 772 700 C 773 770, 776 800, 778 820"
        />

        <!-- HEMISFÉRIO ESQUERDO -->
        <!-- Sulco superior em forma de "C" aberto à direita (parte de cima do lobo frontal esq.) -->
        <path
          id="bt-pL1"
          d="M 560 260 C 595 215, 700 210, 720 280 C 735 350, 660 380, 590 380 C 555 380, 560 410, 595 430"
        />
        <!-- Pequena curva intermediária esquerda -->
        <path id="bt-pL2" d="M 555 460 C 605 440, 685 445, 720 470" />
        <!-- Lobo inferior esquerdo (horseshoe abrindo pra cima) -->
        <path
          id="bt-pL3"
          d="M 510 740 C 530 620, 620 560, 720 600 C 750 680, 720 760, 640 770 C 580 775, 530 770, 510 740"
        />

        <!-- HEMISFÉRIO DIREITO (espelho) -->
        <path
          id="bt-pR1"
          d="M 990 260 C 955 215, 850 210, 830 280 C 815 350, 890 380, 960 380 C 995 380, 990 410, 955 430"
        />
        <path id="bt-pR2" d="M 995 460 C 945 440, 865 445, 830 470" />
        <path
          id="bt-pR3"
          d="M 1040 740 C 1020 620, 930 560, 830 600 C 800 680, 830 760, 910 770 C 970 775, 1020 770, 1040 740"
        />
      </defs>

      <!-- BOLINHAS (sem stroke nas paths — somente os pontos andando) -->
      <!-- Fissura central -->
      <circle r="14" fill="url(#bt-dot)">
        <animateMotion dur="6s" repeatCount="indefinite">
          <mpath href="#bt-pCenter" />
        </animateMotion>
      </circle>

      <!-- Esquerda -->
      <circle r="14" fill="url(#bt-dot)">
        <animateMotion dur="7s" repeatCount="indefinite">
          <mpath href="#bt-pL1" />
        </animateMotion>
      </circle>
      <circle r="14" fill="url(#bt-dot)">
        <animateMotion dur="7s" repeatCount="indefinite" begin="-3.5s">
          <mpath href="#bt-pL1" />
        </animateMotion>
      </circle>
      <circle r="12" fill="url(#bt-dot)">
        <animateMotion dur="4s" repeatCount="indefinite">
          <mpath href="#bt-pL2" />
        </animateMotion>
      </circle>
      <circle r="14" fill="url(#bt-dot)">
        <animateMotion dur="9s" repeatCount="indefinite">
          <mpath href="#bt-pL3" />
        </animateMotion>
      </circle>
      <circle r="14" fill="url(#bt-dot)">
        <animateMotion dur="9s" repeatCount="indefinite" begin="-4.5s">
          <mpath href="#bt-pL3" />
        </animateMotion>
      </circle>

      <!-- Direita -->
      <circle r="14" fill="url(#bt-dot)">
        <animateMotion dur="7s" repeatCount="indefinite" begin="-1.5s">
          <mpath href="#bt-pR1" />
        </animateMotion>
      </circle>
      <circle r="14" fill="url(#bt-dot)">
        <animateMotion dur="7s" repeatCount="indefinite" begin="-5s">
          <mpath href="#bt-pR1" />
        </animateMotion>
      </circle>
      <circle r="12" fill="url(#bt-dot)">
        <animateMotion dur="4s" repeatCount="indefinite" begin="-2s">
          <mpath href="#bt-pR2" />
        </animateMotion>
      </circle>
      <circle r="14" fill="url(#bt-dot)">
        <animateMotion dur="9s" repeatCount="indefinite" begin="-2s">
          <mpath href="#bt-pR3" />
        </animateMotion>
      </circle>
      <circle r="14" fill="url(#bt-dot)">
        <animateMotion dur="9s" repeatCount="indefinite" begin="-6.5s">
          <mpath href="#bt-pR3" />
        </animateMotion>
      </circle>
    </svg>
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
  content: "";
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
  content: "";
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

/* Bolinhas verdes percorrendo APENAS os sulcos reais já desenhados na imagem.
   Overlay tem EXATAMENTE as mesmas dimensões e posição do <img> (320px × 213.33px,
   centralizado no stage), então as coords do viewBox 1536x1024 batem com o pixel real. */
.brain-trails {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 320px;
  height: calc(320px * 1024 / 1536); /* 213.33px — match brain-img aspect */
  pointer-events: none;
  z-index: 2;
  overflow: visible;
  filter: drop-shadow(0 0 3px rgba(61, 242, 75, 1))
    drop-shadow(0 0 8px rgba(61, 242, 75, 0.7))
    drop-shadow(0 0 18px rgba(61, 242, 75, 0.35));
}

@media (prefers-reduced-motion: reduce) {
  .brain-trails animateMotion {
    /* SVG não suporta CSS pra parar animateMotion universalmente,
       mas modernos respeitam quando desligamos via display do parent */
  }
  .brain-trails {
    display: none;
  }
}
</style>
