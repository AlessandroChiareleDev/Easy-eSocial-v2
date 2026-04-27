<script setup lang="ts">
import { ref } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import BrainStage from "@/components/base/BrainStage.vue";

const username = ref("");
const senha = ref("");
const showPwd = ref(false);

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

async function submit() {
  if (!username.value || !senha.value) return;
  try {
    await auth.login(username.value.trim(), senha.value);
    const redirect = (route.query.redirect as string) || "/";
    router.replace(redirect);
  } catch {
    // erro já vai pro auth.error
  }
}

type OAuthProvider = "google" | "github" | "apple";
function loginWith(provider: OAuthProvider) {
  // TODO: integrar com backend OAuth (redirect /api/auth/<provider>)
  // Stub UI: por enquanto apenas sinaliza no console e mostra aviso.
  console.info(`[oauth] iniciando login via ${provider}`);
  alert(`Login via ${provider} ainda não está habilitado neste ambiente.`);
}
</script>

<template>
  <div class="root">
    <!-- Animated glassmorphism shapes — cobrem a tela inteira -->
    <div class="shapes-layer" aria-hidden="true">
      <div class="glass-shape shape-1"></div>
      <div class="glass-shape shape-2"></div>
      <div class="glass-shape shape-3"></div>
      <div class="glass-shape shape-4"></div>
      <div class="glass-shape shape-5"></div>
      <div class="glass-shape shape-6"></div>
      <div class="glass-shape shape-7"></div>
      <div class="glass-shape shape-8"></div>
    </div>

    <!-- Left Brand Panel (60%) -->
    <div class="brand-panel">
      <div class="brand-content">
        <div class="brain-wrap">
          <BrainStage />
        </div>
        <h1 class="brand-title">
          Easy<br /><span class="brand-title-accent">e-Social</span>
        </h1>
        <p class="brand-sub">Gestão eSocial simplificada</p>
      </div>
    </div>

    <!-- Right Form Panel (40%) -->
    <div class="form-panel">
      <div class="form-inner">
        <!-- Mobile brand -->
        <div class="mobile-brand">
          <div class="brain-wrap brain-wrap--mobile">
            <BrainStage />
          </div>
          <h1 class="brand-title brand-title--mobile">
            Easy<br /><span class="brand-title-accent">e-Social</span>
          </h1>
        </div>

        <h2 class="form-title">Entrar</h2>
        <p class="form-sub">Acesse sua conta Easy e-Social</p>

        <div v-if="auth.error" class="err-banner" role="alert">
          <svg
            class="err-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="15" y1="9" x2="9" y2="15" />
            <line x1="9" y1="9" x2="15" y2="15" />
          </svg>
          {{ auth.error }}
        </div>

        <form @submit.prevent="submit" class="form-stack" novalidate>
          <div class="field-group">
            <label for="usuario" class="field-label">Usuário</label>
            <div class="input-wrap">
              <span class="input-icon">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
              </span>
              <input
                id="usuario"
                v-model="username"
                type="text"
                required
                autocomplete="username"
                placeholder="Seu usuário"
                :disabled="auth.loading"
                class="input-text input-text--with-icon"
              />
            </div>
          </div>

          <div class="field-group">
            <label for="senha" class="field-label">Senha</label>
            <div class="input-wrap">
              <input
                id="senha"
                v-model="senha"
                :type="showPwd ? 'text' : 'password'"
                required
                autocomplete="current-password"
                placeholder="••••••••"
                :disabled="auth.loading"
                class="input-text input-text--with-toggle"
              />
              <button
                type="button"
                class="input-toggle"
                @click="showPwd = !showPwd"
                :aria-label="showPwd ? 'Ocultar senha' : 'Mostrar senha'"
              >
                <svg
                  v-if="!showPwd"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
                <svg
                  v-else
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path
                    d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"
                  />
                  <line x1="1" y1="1" x2="23" y2="23" />
                </svg>
              </button>
            </div>
          </div>

          <button type="submit" :disabled="auth.loading" class="btn-submit">
            <svg
              v-if="auth.loading"
              class="btn-spin"
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                stroke-width="3"
                class="op-25"
              />
              <path
                d="M4 12a8 8 0 0 1 8-8"
                stroke="currentColor"
                stroke-width="3"
                stroke-linecap="round"
                class="op-75"
              />
            </svg>
            <span v-else>Entrar</span>
          </button>
        </form>

        <div class="divider" role="separator" aria-label="ou continue com">
          <span>ou continue com</span>
        </div>

        <div class="oauth-row">
          <button
            type="button"
            class="btn-oauth"
            :disabled="auth.loading"
            @click="loginWith('google')"
            aria-label="Entrar com Google"
          >
            <svg viewBox="0 0 48 48" aria-hidden="true">
              <path
                fill="#FFC107"
                d="M43.6 20.5H42V20H24v8h11.3c-1.6 4.7-6.1 8-11.3 8-6.6 0-12-5.4-12-12s5.4-12 12-12c3 0 5.8 1.1 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"
              />
              <path
                fill="#FF3D00"
                d="M6.3 14.1l6.6 4.8C14.7 15.1 19 12 24 12c3 0 5.8 1.1 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.1z"
              />
              <path
                fill="#4CAF50"
                d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.6 39.6 16.2 44 24 44z"
              />
              <path
                fill="#1976D2"
                d="M43.6 20.5H42V20H24v8h11.3c-.8 2.3-2.3 4.3-4.2 5.6l6.2 5.2C41.4 35.5 44 30.2 44 24c0-1.3-.1-2.4-.4-3.5z"
              />
            </svg>
            <span>Google</span>
          </button>

          <button
            type="button"
            class="btn-oauth"
            :disabled="auth.loading"
            @click="loginWith('github')"
            aria-label="Entrar com GitHub"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path
                fill="currentColor"
                d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.92.58.1.79-.25.79-.56 0-.28-.01-1.02-.02-2-3.2.7-3.87-1.54-3.87-1.54-.52-1.32-1.27-1.67-1.27-1.67-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.02 1.75 2.68 1.24 3.34.95.1-.74.4-1.24.73-1.53-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.28 1.18-3.09-.12-.29-.51-1.46.11-3.04 0 0 .97-.31 3.18 1.18a11.06 11.06 0 0 1 5.79 0c2.21-1.49 3.18-1.18 3.18-1.18.62 1.58.23 2.75.11 3.04.74.81 1.18 1.83 1.18 3.09 0 4.42-2.69 5.39-5.25 5.68.41.36.78 1.05.78 2.12 0 1.53-.01 2.77-.01 3.14 0 .31.21.67.8.56C20.21 21.39 23.5 17.08 23.5 12 23.5 5.65 18.35.5 12 .5z"
              />
            </svg>
            <span>GitHub</span>
          </button>

          <button
            type="button"
            class="btn-oauth"
            :disabled="auth.loading"
            @click="loginWith('apple')"
            aria-label="Entrar com Apple"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path
                fill="currentColor"
                d="M16.37 1.43c0 1.14-.42 2.22-1.13 3.02-.78.9-2.05 1.6-3.07 1.52-.13-1.1.42-2.24 1.1-3.01.78-.88 2.1-1.55 3.1-1.53zM20.5 17.27c-.55 1.27-.82 1.84-1.53 2.97-.99 1.57-2.39 3.52-4.12 3.54-1.54.02-1.94-1-4.04-.99-2.1.01-2.53 1-4.07.98-1.73-.02-3.06-1.78-4.05-3.34C.04 16.06-.25 10.96 1.43 8.25 2.62 6.32 4.5 5.2 6.27 5.2c1.8 0 2.94 1 4.43 1 1.45 0 2.33-1 4.42-1 1.57 0 3.24.85 4.43 2.32-3.9 2.13-3.27 7.7.95 9.75z"
              />
            </svg>
            <span>Apple</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ============================================================
   Layout — UM único fundo animado pra tela toda. Os dois
   "painéis" são transparentes, então não há corte/diferença
   entre os lados — só o form vira um card de vidro flutuante.
   ============================================================ */
.root {
  display: flex;
  min-height: 100vh;
  position: relative;
  overflow: hidden;
  background: linear-gradient(
    135deg,
    #0a0d14,
    #0f1320,
    rgba(61, 242, 75, 0.18),
    #1a0e18,
    #0a0d14
  );
  background-size: 400% 400%;
  animation: bgShift 16s ease-in-out infinite;
}
/* Vinheta radial pra dar profundidade no canto direito (onde o form fica) */
.root::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(
    ellipse 60% 80% at 80% 50%,
    rgba(0, 0, 0, 0.45) 0%,
    transparent 70%
  );
  z-index: 0;
}
@keyframes bgShift {
  0% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}

/* Brand panel: ocupa tela inteira, conteúdo fica centrado no meio absoluto.
   O form vira overlay sobre o lado direito (ver .form-panel). */
.brand-panel {
  display: none;
  position: absolute;
  inset: 0;
  align-items: center;
  justify-content: center;
  z-index: 1;
}
@media (min-width: 1024px) {
  .brand-panel {
    display: flex;
  }
}

/* shapes-layer agora cobre a TELA inteira pra não ter borda nenhuma
   onde as shapes sumam ao passar do limite dos painéis. */
.shapes-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}

.brand-content {
  position: relative;
  z-index: 10;
  text-align: center;
  padding: 0 64px;
  max-width: 32rem;
}
.brain-wrap {
  display: grid;
  place-items: center;
  margin: 0 auto 24px;
  width: 360px;
  max-width: 100%;
}
.brain-wrap--mobile {
  width: 220px;
  margin-bottom: 8px;
}
.brand-title {
  font-size: 36px;
  font-weight: 700;
  color: #fff;
  margin: 0 0 12px;
  letter-spacing: -0.02em;
  line-height: 1.05;
}
.brand-title--mobile {
  font-size: 24px;
}
.brand-title-accent {
  color: var(--secondary);
  text-shadow: 0 0 22px rgba(61, 242, 75, 0.55);
}
.brand-sub {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.6);
  margin: 0;
}

/* Form panel: transparente, só centraliza o card. No desktop fica
   ancorado à direita pra não competir com o brand centralizado. */
.form-panel {
  position: relative;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  z-index: 2;
}
@media (min-width: 1024px) {
  .form-panel {
    margin-left: auto;
    width: 40%;
    flex: 0 0 40%;
    justify-content: center;
  }
}
.form-inner {
  position: relative;
  width: 100%;
  max-width: 24rem;
  text-align: center;
  padding: 40px 36px;
  border-radius: 20px;
  background: rgba(11, 14, 20, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.06);
  box-shadow:
    0 30px 80px -20px rgba(0, 0, 0, 0.6),
    0 0 0 1px rgba(61, 242, 75, 0.04),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(24px) saturate(1.2);
  -webkit-backdrop-filter: blur(24px) saturate(1.2);
}
.mobile-brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  text-align: center;
  margin-bottom: 32px;
}
@media (min-width: 1024px) {
  .mobile-brand {
    display: none;
  }
}

/* ============================================================
   Glass shapes (Ghost Green)
   ============================================================ */
.glass-shape {
  position: absolute;
  border: 1.5px solid rgba(61, 242, 75, 0.25);
  background: rgba(61, 242, 75, 0.06);
  box-shadow:
    0 0 15px rgba(61, 242, 75, 0.3),
    0 0 40px rgba(61, 242, 75, 0.18),
    0 0 80px rgba(61, 242, 75, 0.08),
    inset 0 0 20px rgba(61, 242, 75, 0.04);
  will-change: transform;
}

.shape-1 {
  width: 280px;
  height: 280px;
  border-radius: 50%;
  filter: blur(2px);
  animation: drift1 26s ease-in-out infinite;
}
@keyframes drift1 {
  0% {
    transform: translate(-10%, -15%) rotate(0deg);
  }
  50% {
    transform: translate(40%, 70%) rotate(30deg);
  }
  100% {
    transform: translate(-10%, -15%) rotate(0deg);
  }
}

.shape-2 {
  width: 200px;
  height: 200px;
  border-radius: 32px;
  filter: blur(1.5px);
  right: -40px;
  animation: drift2 30s ease-in-out infinite;
}
@keyframes drift2 {
  0% {
    transform: translate(10%, -20%) rotate(45deg);
  }
  50% {
    transform: translate(-50%, 80%) rotate(90deg);
  }
  100% {
    transform: translate(10%, -20%) rotate(45deg);
  }
}

.shape-3 {
  width: 160px;
  height: 160px;
  border-radius: 50%;
  filter: blur(3px);
  left: 55%;
  animation: drift3 22s ease-in-out infinite;
  animation-delay: -8s;
}
@keyframes drift3 {
  0% {
    transform: translate(0, -30%) rotate(0deg);
  }
  50% {
    transform: translate(-30%, 90%) rotate(-20deg);
  }
  100% {
    transform: translate(0, -30%) rotate(0deg);
  }
}

.shape-4 {
  width: 100px;
  height: 100px;
  border-radius: 20px;
  filter: blur(1px);
  left: 30%;
  animation: drift4 18s ease-in-out infinite;
  animation-delay: -4s;
}
@keyframes drift4 {
  0% {
    transform: translate(0, -10%) rotate(12deg);
  }
  50% {
    transform: translate(20%, 100%) rotate(60deg);
  }
  100% {
    transform: translate(0, -10%) rotate(12deg);
  }
}

.shape-5 {
  width: 240px;
  height: 180px;
  border-radius: 40px;
  filter: blur(2.5px);
  left: 10%;
  bottom: 0;
  animation: drift5 34s ease-in-out infinite;
  animation-delay: -12s;
}
@keyframes drift5 {
  0% {
    transform: translate(-5%, 20%) rotate(-8deg);
  }
  50% {
    transform: translate(30%, -80%) rotate(15deg);
  }
  100% {
    transform: translate(-5%, 20%) rotate(-8deg);
  }
}

.shape-6 {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  filter: blur(1px);
  left: 70%;
  top: 60%;
  border-color: rgba(61, 242, 75, 0.4);
  box-shadow:
    0 0 20px rgba(61, 242, 75, 0.4),
    0 0 50px rgba(61, 242, 75, 0.2),
    0 0 80px rgba(61, 242, 75, 0.1);
  animation: drift6 15s ease-in-out infinite;
  animation-delay: -6s;
}
@keyframes drift6 {
  0% {
    transform: translate(0, 0) rotate(0deg);
  }
  50% {
    transform: translate(-40%, -120%) rotate(45deg);
  }
  100% {
    transform: translate(0, 0) rotate(0deg);
  }
}

.shape-7 {
  width: 140px;
  height: 140px;
  border-radius: 28px;
  filter: blur(2px);
  right: 15%;
  top: 20%;
  animation: drift7 24s ease-in-out infinite;
  animation-delay: -10s;
}
@keyframes drift7 {
  0% {
    transform: translate(10%, -5%) rotate(-12deg);
  }
  50% {
    transform: translate(-20%, 75%) rotate(25deg);
  }
  100% {
    transform: translate(10%, -5%) rotate(-12deg);
  }
}

.shape-8 {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  filter: blur(0.5px);
  left: 20%;
  top: 40%;
  border-color: rgba(61, 242, 75, 0.45);
  box-shadow:
    0 0 18px rgba(61, 242, 75, 0.45),
    0 0 45px rgba(61, 242, 75, 0.22),
    0 0 70px rgba(61, 242, 75, 0.1);
  animation: drift8 13s ease-in-out infinite;
  animation-delay: -3s;
}
@keyframes drift8 {
  0% {
    transform: translate(0, 0) rotate(0deg);
  }
  50% {
    transform: translate(50%, 110%) rotate(-30deg);
  }
  100% {
    transform: translate(0, 0) rotate(0deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .root,
  .glass-shape {
    animation: none !important;
  }
}

/* ============================================================
   Form
   ============================================================ */
.form-title {
  font-size: 28px;
  font-weight: 700;
  color: #fff;
  margin: 0;
  text-align: center;
  letter-spacing: -0.01em;
}
.form-sub {
  font-size: 13px;
  color: var(--text-muted);
  margin: 6px 0 28px;
  text-align: center;
}
.form-stack {
  display: flex;
  flex-direction: column;
  gap: 18px;
  text-align: left;
}

.field-group {
  display: block;
}
.field-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.input-wrap {
  position: relative;
}
.input-icon {
  position: absolute;
  left: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  pointer-events: none;
}
.input-icon svg {
  width: 20px;
  height: 20px;
  display: block;
}

.input-text {
  width: 100%;
  height: 44px;
  padding: 0 16px;
  font-size: 14px;
  font-family: inherit;
  color: #fff;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  outline: none;
  transition:
    border-color var(--duration-base) var(--ease-glass),
    box-shadow var(--duration-base) var(--ease-glass);
}
.input-text::placeholder {
  color: var(--text-muted);
}
.input-text--with-icon {
  padding-left: 44px;
}
.input-text--with-toggle {
  padding-right: 44px;
}
.input-text:focus {
  border-color: rgba(61, 242, 75, 0.5);
  box-shadow:
    0 0 0 3px rgba(61, 242, 75, 0.12),
    0 0 18px rgba(61, 242, 75, 0.18);
}
.input-text:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.input-toggle {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  background: transparent;
  border: 0;
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px;
  display: grid;
  place-items: center;
  transition: color 0.15s;
}
.input-toggle:hover {
  color: var(--text-primary);
}
.input-toggle svg {
  width: 20px;
  height: 20px;
  display: block;
}

.btn-submit {
  width: 100%;
  height: 48px;
  background: var(--secondary);
  color: #062a09;
  font-weight: 700;
  letter-spacing: 0.02em;
  font-size: 15px;
  border: 0;
  border-radius: 10px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow:
    0 0 24px rgba(61, 242, 75, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.25);
  transition:
    background 0.15s,
    transform 0.15s,
    box-shadow 0.15s;
}
.btn-submit:hover:not(:disabled) {
  background: #5cf968;
  transform: translateY(-1px);
  box-shadow:
    0 0 32px rgba(61, 242, 75, 0.5),
    inset 0 1px 0 rgba(255, 255, 255, 0.3);
}
.btn-submit:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.btn-spin {
  width: 20px;
  height: 20px;
  animation: spin 0.8s linear infinite;
}
.op-25 {
  opacity: 0.25;
}
.op-75 {
  opacity: 0.75;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.err-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  margin-bottom: 24px;
  background: rgba(255, 100, 130, 0.08);
  border: 1px solid rgba(255, 100, 130, 0.3);
  border-radius: 10px;
  color: #ff8aa8;
  font-size: 13px;
}
.err-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

/* ============================================================
   OAuth (Google / GitHub / Apple)
   ============================================================ */
.divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 24px 0 16px;
  color: var(--text-muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.divider::before,
.divider::after {
  content: "";
  flex: 1;
  height: 1px;
  background: linear-gradient(
    to right,
    transparent,
    rgba(255, 255, 255, 0.12),
    transparent
  );
}

.oauth-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.btn-oauth {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 44px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition:
    background-color 0.18s ease,
    border-color 0.18s ease,
    transform 0.18s ease,
    box-shadow 0.18s ease;
}
.btn-oauth:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(61, 242, 75, 0.35);
  box-shadow:
    0 0 0 1px rgba(61, 242, 75, 0.12),
    0 4px 14px rgba(0, 0, 0, 0.35);
  transform: translateY(-1px);
}
.btn-oauth:active:not(:disabled) {
  transform: translateY(0);
}
.btn-oauth:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-oauth svg {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

@media (max-width: 480px) {
  .oauth-row {
    grid-template-columns: 1fr;
  }
  .btn-oauth {
    height: 42px;
  }
}
</style>
