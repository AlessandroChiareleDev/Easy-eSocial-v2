<script setup lang="ts">
import { computed } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useEmpresaStore, type Empresa } from "@/stores/empresa";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const route = useRoute();
const store = useEmpresaStore();
const auth = useAuthStore();

const empresas = computed<Empresa[]>(() => store.lista);

function escolher(emp: Empresa): void {
  if (emp.ativo === false) return;
  store.setEmpresa(emp);
  const redirect = (route.query.redirect as string) || "/";
  router.replace(redirect);
}

function fmtCnpj(c: string): string {
  if (!c) return "—";
  const d = c.replace(/\D/g, "");
  if (d.length !== 14) return c;
  return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`;
}
</script>

<template>
  <div class="empresa-select">
    <header class="head">
      <h1>Escolha a empresa</h1>
      <p class="sub">
        Cada empresa tem seu próprio schema isolado no banco. Os dados que
        você vai ver dependem da escolha aqui.
      </p>
      <p v-if="auth.user" class="who">
        Logado como <strong>{{ auth.user.email }}</strong>
        <span v-if="auth.isSuperAdmin" class="super">super admin</span>
      </p>
    </header>

    <div v-if="empresas.length === 0" class="state">
      Nenhuma empresa vinculada ao seu usuário.
    </div>

    <div v-else class="cards">
      <button
        v-for="emp in empresas"
        :key="emp.cnpj"
        class="card"
        :class="{ inativo: emp.ativo === false }"
        :disabled="emp.ativo === false"
        @click="escolher(emp)"
      >
        <div class="badge-row">
          <span class="badge papel">{{ emp.papel }}</span>
          <span
            class="badge status"
            :class="{ ok: emp.ativo !== false, no: emp.ativo === false }"
          >
            {{ emp.ativo === false ? "inativa" : "ativa" }}
          </span>
        </div>
        <div class="logo">{{ (emp.razao_social || emp.cnpj).charAt(0) }}</div>
        <h2 class="nome">{{ emp.razao_social || emp.schema_name || emp.cnpj }}</h2>
        <div class="cnpj">CNPJ {{ fmtCnpj(emp.cnpj) }}</div>
        <div class="meta">schema: {{ emp.schema_name || "—" }}</div>
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
.card.inativo {
  border-style: dashed;
  border-color: rgba(148, 163, 184, 0.25);
  opacity: 0.5;
  cursor: not-allowed;
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
.badge.papel {
  background: rgba(96, 165, 250, 0.15);
  color: #93c5fd;
}
.badge.status.ok {
  background: rgba(34, 197, 94, 0.15);
  color: #86efac;
}
.badge.status.no {
  background: rgba(248, 113, 113, 0.15);
  color: #fca5a5;
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
