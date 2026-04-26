<script setup lang="ts">
import BrainStage from '@/components/base/BrainStage.vue';
import { RouterLink } from 'vue-router';
</script>

<template>
  <main class="page">
    <header class="hero">
      <div class="crumb">Cérebro Operacional · APPA · 2026</div>
      <h1>
        Boa noite, <span class="name-grad">Xandão</span>
      </h1>
      <p class="sub">26 de abril de 2026 · sincronizado há 2 min</p>
    </header>

    <section class="brain-section">
      <BrainStage />
    </section>

    <section class="grid">
      <RouterLink to="/tabelas" class="opt liquid-glass">
        <div class="opt-num">01</div>
        <div class="opt-title">Tabelas</div>
        <div class="opt-desc">S-1000 · S-1005 · S-1010 · rubricas, lotações, estabelecimentos</div>
      </RouterLink>

      <RouterLink to="/esocial/s1010" class="opt liquid-glass">
        <div class="opt-num">02</div>
        <div class="opt-title">eSocial S-1010</div>
        <div class="opt-desc">rubricas · webservice · envio</div>
      </RouterLink>

      <RouterLink to="/esocial/s1210-anual" class="opt liquid-glass">
        <div class="opt-num">03</div>
        <div class="opt-title">S-1210 Anual</div>
        <div class="opt-desc">
          22.580 eventos 2025 · <span class="gg-glow">99.84%</span> ok
        </div>
      </RouterLink>

      <RouterLink to="/logs" class="opt liquid-glass">
        <div class="opt-num">04</div>
        <div class="opt-title">Logs de Sistema</div>
        <div class="opt-desc">auditoria · histórico · respostas eSocial</div>
      </RouterLink>

      <RouterLink to="/problemas" class="opt liquid-glass">
        <div class="opt-num">05</div>
        <div class="opt-title">Problemas</div>
        <div class="opt-desc">erros L1 / L2 · pendências · reenvios</div>
      </RouterLink>
    </section>
  </main>
</template>

<style scoped>
.page {
  max-width: 1180px;
  margin: 0 auto;
  padding: 56px 32px 96px;
}

.hero {
  text-align: center;
  margin-bottom: 12px;
}
.crumb {
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 10.5px;
  color: var(--text-muted);
  letter-spacing: 0.18em;
  text-transform: uppercase;
  margin-bottom: 10px;
}
.hero h1 {
  font-size: 30px;
  font-weight: 500;
  letter-spacing: -0.02em;
  margin: 0;
}
.name-grad {
  background: linear-gradient(90deg, #fff 0%, var(--primary) 60%, #c89bb8 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.sub {
  margin-top: 6px;
  font-size: 13px;
  color: var(--text-muted);
  font-family: 'Geist Mono', ui-monospace, monospace;
  letter-spacing: 0.04em;
}

.brain-section {
  display: grid;
  place-items: center;
  margin: 24px 0 36px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 18px;
}

.opt {
  display: block;
  padding: 22px;
  text-decoration: none;
  color: inherit;
  transition: transform var(--duration-base) var(--ease-glass),
    box-shadow var(--duration-base) var(--ease-glass);
}
.opt:hover {
  transform: translateY(-3px);
  box-shadow:
    0 18px 50px rgba(0, 0, 0, 0.6),
    0 0 0 1px rgba(61, 242, 75, 0.3),
    0 0 36px rgba(61, 242, 75, 0.18),
    inset 0 1px 0 rgba(240, 209, 229, 0.22);
}
.opt-num {
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 10.5px;
  color: var(--text-muted);
  letter-spacing: 0.18em;
  text-transform: uppercase;
  margin-bottom: 12px;
}
.opt-title {
  font-size: 17px;
  font-weight: 600;
  letter-spacing: -0.01em;
  margin-bottom: 4px;
}
.opt-desc {
  font-size: 12.5px;
  color: var(--text-muted);
  line-height: 1.55;
  font-family: 'Geist Mono', ui-monospace, monospace;
}
</style>
