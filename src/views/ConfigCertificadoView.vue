<script setup lang="ts">
/**
 * F9.8 — ConfigCertificado
 *
 * Lista certificados, mostra ativo, permite delete e upload de novo.
 * Backend:
 *   GET    /api/certificados/listar
 *   GET    /api/certificados/ativo
 *   DELETE /api/certificados/{id}
 */
import { onMounted, ref, computed } from "vue";
import { api, type ApiError } from "@/services/api";
import CertificadoUpload from "@/components/CertificadoUpload.vue";

interface Certificado {
  id: number;
  cnpj: string;
  titular: string;
  emissor?: string;
  numero_serie: string;
  validade_fim: string;
  ativo: boolean;
  created_at?: string;
}

const lista = ref<Certificado[]>([]);
const loading = ref(false);
const erro = ref<string | null>(null);

async function carregar() {
  loading.value = true;
  erro.value = null;
  try {
    const res = await api.get<{ certificados: Certificado[] } | Certificado[]>(
      "/certificados/listar",
    );
    lista.value = Array.isArray(res) ? res : (res.certificados ?? []);
  } catch (e) {
    erro.value = e instanceof Error ? e.message : "Falha ao listar";
    lista.value = [];
  } finally {
    loading.value = false;
  }
}

async function remover(c: Certificado) {
  const cn = c.titular || c.cnpj;
  if (
    !confirm(`Remover certificado de ${cn}? Essa ação não pode ser desfeita.`)
  ) {
    return;
  }
  try {
    await api.del(`/certificados/${c.id}`);
    await carregar();
  } catch (e) {
    const ae = e as ApiError;
    alert(`Falha: ${ae.message}`);
  }
}

const ativo = computed(() => lista.value.find((c) => c.ativo) ?? null);
const inativos = computed(() => lista.value.filter((c) => !c.ativo));

function fmtCnpj(c: string): string {
  if (!c) return "—";
  const d = c.replace(/\D/g, "");
  if (d.length !== 14) return c;
  return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`;
}

function fmtDate(s: string): string {
  if (!s) return "—";
  try {
    return new Date(s).toLocaleDateString("pt-BR");
  } catch {
    return s;
  }
}

function diasRestantes(s: string): number | null {
  if (!s) return null;
  const d = new Date(s).getTime() - Date.now();
  if (Number.isNaN(d)) return null;
  return Math.floor(d / 86400000);
}

onMounted(() => {
  void carregar();
});
</script>

<template>
  <div class="config-cert">
    <header class="head">
      <h1>Certificado A1</h1>
      <p class="sub">
        Certificado digital usado para assinar e enviar eventos ao eSocial.
        Apenas <strong>1</strong> ativo por vez.
      </p>
    </header>

    <section class="grid">
      <div class="col">
        <h2 class="sec-title">Ativo agora</h2>
        <div v-if="loading && !ativo" class="state">Carregando…</div>
        <div v-else-if="!ativo" class="state empty">
          Nenhum certificado ativo. Faça upload para começar.
        </div>
        <div v-else class="cert-card ativo">
          <div class="badge ok">ativo</div>
          <div class="titular">{{ ativo.titular || "—" }}</div>
          <div class="cnpj">CNPJ {{ fmtCnpj(ativo.cnpj) }}</div>
          <div class="meta">
            <div>Emissor: {{ ativo.emissor || "—" }}</div>
            <div>Série: {{ ativo.numero_serie }}</div>
            <div>
              Validade: {{ fmtDate(ativo.validade_fim) }}
              <span
                v-if="diasRestantes(ativo.validade_fim) !== null"
                class="dias"
                :class="{
                  warn: (diasRestantes(ativo.validade_fim) ?? 99) < 30,
                  err: (diasRestantes(ativo.validade_fim) ?? 99) < 0,
                }"
              >
                ({{ diasRestantes(ativo.validade_fim) }} dias)
              </span>
            </div>
          </div>
          <button class="btn-del" @click="remover(ativo)">Remover</button>
        </div>

        <h2 v-if="inativos.length" class="sec-title spaced">Histórico</h2>
        <ul v-if="inativos.length" class="historico">
          <li v-for="c in inativos" :key="c.id">
            <div class="hist-line">
              <span class="hist-titular">{{ c.titular || c.cnpj }}</span>
              <span class="hist-validade"
                >até {{ fmtDate(c.validade_fim) }}</span
              >
              <button class="btn-del-mini" @click="remover(c)">excluir</button>
            </div>
          </li>
        </ul>
      </div>

      <div class="col">
        <CertificadoUpload @uploaded="carregar" />
      </div>
    </section>

    <div v-if="erro" class="banner err">{{ erro }}</div>
  </div>
</template>

<style scoped>
.config-cert {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 24px;
  color: #e6e9f2;
}
.head h1 {
  margin: 0 0 8px;
  font-size: 1.8rem;
}
.head .sub {
  margin: 0 0 32px;
  color: #94a3b8;
  max-width: 640px;
}
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 32px;
}
@media (max-width: 900px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
.sec-title {
  margin: 0 0 16px;
  font-size: 1rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #94a3b8;
}
.sec-title.spaced {
  margin-top: 32px;
}
.state {
  padding: 32px;
  text-align: center;
  color: #94a3b8;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 12px;
  border: 1px dashed rgba(148, 163, 184, 0.25);
}
.state.empty {
  font-style: italic;
}
.cert-card {
  background: linear-gradient(
    160deg,
    rgba(30, 41, 59, 0.85),
    rgba(15, 23, 42, 0.9)
  );
  border: 1px solid rgba(34, 197, 94, 0.4);
  border-radius: 14px;
  padding: 24px;
  position: relative;
}
.badge {
  position: absolute;
  top: 16px;
  right: 16px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.badge.ok {
  background: rgba(34, 197, 94, 0.2);
  color: #86efac;
}
.titular {
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 4px;
}
.cnpj {
  color: #cbd5e1;
  font-variant-numeric: tabular-nums;
  font-size: 0.9rem;
  margin-bottom: 16px;
}
.meta {
  font-size: 0.85rem;
  color: #94a3b8;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.dias {
  color: #86efac;
  font-weight: 600;
}
.dias.warn {
  color: #fbbf24;
}
.dias.err {
  color: #fca5a5;
}
.btn-del {
  margin-top: 20px;
  background: rgba(248, 113, 113, 0.15);
  color: #fca5a5;
  border: 1px solid rgba(248, 113, 113, 0.3);
  padding: 8px 14px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.85rem;
}
.historico {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.hist-line {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  font-size: 0.85rem;
}
.hist-titular {
  flex: 1;
}
.hist-validade {
  color: #94a3b8;
}
.btn-del-mini {
  background: transparent;
  border: none;
  color: #fca5a5;
  cursor: pointer;
  font-size: 0.8rem;
  text-decoration: underline;
}
.banner.err {
  margin-top: 24px;
  padding: 12px 16px;
  border-radius: 8px;
  background: rgba(248, 113, 113, 0.15);
  color: #fca5a5;
  border: 1px solid rgba(248, 113, 113, 0.3);
}
</style>
