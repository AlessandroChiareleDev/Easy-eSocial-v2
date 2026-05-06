<script setup lang="ts">
import { onMounted, computed } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useEmpresaStore, type Empresa } from "@/stores/empresa";

const router = useRouter();
const route = useRoute();
const store = useEmpresaStore();

onMounted(() => {
  void store.carregar();
});

const empresas = computed<Empresa[]>(() => store.lista);

function escolher(emp: Empresa): void {
  store.setEmpresa(emp);
  const redirect = (route.query.redirect as string) || "/";
  router.replace(redirect);
}

function fmtCnpj(c: string): string {
  return c || "—";
}
</script>

<template>
  <div class="empresa-select">
    <header class="head">
      <h1>Escolha a empresa</h1>
      <p class="sub">
        Cada empresa tem seu próprio banco de dados isolado. Os dados que você
        vai ver dependem da escolha aqui.
      </p>
    </header>

    <div v-if="store.loading" class="state">Carregando empresas…</div>
    <div v-else-if="store.error" class="state error">
      Falha ao carregar empresas: {{ store.error }}
    </div>
    <div v-else-if="empresas.length === 0" class="state">
      Nenhuma empresa ativa cadastrada.
    </div>

    <div v-else class="cards">
      <button
        v-for="emp in empresas"
        :key="emp.id"
        class="card"
        :class="{ vazio: !emp.tem_dados }"
        @click="escolher(emp)"
      >
        <div class="badge-row">
          <span class="badge db" :class="emp.db_kind">{{ emp.db_kind }}</span>
          <span
            class="badge dados"
            :class="{ ok: emp.tem_dados, no: !emp.tem_dados }"
          >
            {{ emp.tem_dados ? "com dados" : "vazia" }}
          </span>
        </div>
        <div class="logo">{{ emp.nome.charAt(0) }}</div>
        <h2 class="nome">{{ emp.nome }}</h2>
        <div class="cnpj">CNPJ {{ fmtCnpj(emp.cnpj) }}</div>
        <div v-if="emp.tem_dados" class="meta">
          {{ emp.envios_count?.toLocaleString("pt-BR") ?? 0 }} envios ·
          {{ emp.xlsx_count ?? 0 }} XLSX
        </div>
        <div v-else class="meta muted">
          banco recém-criado, sem operação ainda
        </div>
        <span class="cta">Entrar →</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.empresa-select {
  max-width: 1100px;
  margin: 0 auto;
  padding: 64px 24px;
  color: #e6e9f2;
}
.head h1 {
  font-size: 2rem;
  margin: 0 0 8px;
  letter-spacing: -0.01em;
}
.head .sub {
  margin: 0 0 40px;
  color: #94a3b8;
  max-width: 640px;
}
.state {
  padding: 40px;
  text-align: center;
  color: #94a3b8;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 12px;
}
.state.error {
  color: #fca5a5;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 24px;
}
.card {
  position: relative;
  text-align: left;
  background: linear-gradient(
    160deg,
    rgba(30, 41, 59, 0.85),
    rgba(15, 23, 42, 0.9)
  );
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 16px;
  padding: 28px;
  cursor: pointer;
  color: inherit;
  font: inherit;
  transition:
    transform 0.15s ease,
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}
.card:hover {
  transform: translateY(-2px);
  border-color: rgba(96, 165, 250, 0.5);
  box-shadow: 0 12px 32px -8px rgba(59, 130, 246, 0.35);
}
.card.vazio {
  border-style: dashed;
  border-color: rgba(148, 163, 184, 0.25);
}
.badge-row {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
}
.badge {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 4px 10px;
  border-radius: 999px;
}
.badge.db.supabase {
  background: rgba(62, 207, 142, 0.15);
  color: #6ee7b7;
}
.badge.db.local {
  background: rgba(96, 165, 250, 0.15);
  color: #93c5fd;
}
.badge.dados.ok {
  background: rgba(34, 197, 94, 0.15);
  color: #86efac;
}
.badge.dados.no {
  background: rgba(148, 163, 184, 0.15);
  color: #cbd5e1;
}
.logo {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  display: grid;
  place-items: center;
  font-size: 1.6rem;
  font-weight: 700;
  margin-bottom: 16px;
}
.nome {
  font-size: 1.15rem;
  margin: 0 0 6px;
  line-height: 1.3;
}
.cnpj {
  color: #94a3b8;
  font-size: 0.85rem;
  margin-bottom: 16px;
  font-variant-numeric: tabular-nums;
}
.meta {
  color: #cbd5e1;
  font-size: 0.85rem;
}
.meta.muted {
  color: #64748b;
  font-style: italic;
}
.cta {
  display: block;
  margin-top: 20px;
  color: #60a5fa;
  font-weight: 600;
  font-size: 0.9rem;
}
</style>
