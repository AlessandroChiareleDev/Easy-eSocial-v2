<script setup lang="ts">
import { ref, watch } from "vue";
import {
  cadeiaCpf,
  type CadeiaResp,
  type CadeiaVersao,
  type CadeiaTentativa,
} from "@/services/exploradorApi";

const props = defineProps<{
  empresaId: number;
  cpf: string | null;
  perApur: string;
  tipoEvento?: string;
}>();
const emit = defineEmits<{ (e: "fechar"): void }>();

const carregando = ref(false);
const erro = ref<string | null>(null);
const dados = ref<CadeiaResp | null>(null);

async function carregar() {
  if (!props.cpf) return;
  carregando.value = true;
  erro.value = null;
  try {
    dados.value = await cadeiaCpf({
      empresaId: props.empresaId,
      cpf: props.cpf,
      perApur: props.perApur,
      tipoEvento: props.tipoEvento,
    });
  } catch (e: any) {
    erro.value = e?.message ?? "falha ao carregar cadeia";
  } finally {
    carregando.value = false;
  }
}

watch(() => props.cpf, carregar, { immediate: true });

function fmtCPF(c: string) {
  const s = c.replace(/\D/g, "").padStart(11, "0");
  return `${s.slice(0, 3)}.${s.slice(3, 6)}.${s.slice(6, 9)}-${s.slice(9, 11)}`;
}
function fmtData(s: string | null) {
  return s ? new Date(s).toLocaleString("pt-BR") : "—";
}
function rotuloVersao(v: CadeiaVersao) {
  if (v.envio_tipo === "zip_inicial") return "v0 (zip inicial)";
  return `v${v.envio_sequencia ?? "?"} (${v.envio_tipo ?? "—"})`;
}
function statusBadge(s: string) {
  return (
    {
      sucesso: "ok",
      erro_esocial: "err",
      falha_rede: "warn",
      rejeitado_local: "warn",
      pendente: "info",
    }[s] ?? "info"
  );
}
</script>

<template>
  <Transition name="drawer">
    <div v-if="cpf" class="overlay" @click.self="emit('fechar')">
      <aside class="drawer liquid-glass-strong">
        <div class="drawer-head">
          <div>
            <div class="ttl">Cadeia do CPF</div>
            <div class="cpf mono">{{ fmtCPF(cpf) }}</div>
            <div class="meta">
              {{ tipoEvento ?? "S-1210" }} · perApur
              <strong>{{ perApur }}</strong>
            </div>
          </div>
          <button class="x" @click="emit('fechar')">✕</button>
        </div>

        <div v-if="carregando" class="state">carregando cadeia…</div>
        <div v-else-if="erro" class="state err">{{ erro }}</div>
        <div v-else-if="dados" class="content">
          <section>
            <h4>Versões na base ({{ dados.versoes.length }})</h4>
            <ol class="versoes">
              <li
                v-for="v in dados.versoes"
                :key="v.id"
                :class="{ head: v.is_head }"
              >
                <div class="v-row">
                  <span class="seq mono">{{ rotuloVersao(v) }}</span>
                  <span v-if="v.is_head" class="head-tag">HEAD 🔒</span>
                  <span v-else class="old-tag">retificada 🔒</span>
                </div>
                <div class="recibo mono">recibo: {{ v.nr_recibo ?? "—" }}</div>
                <div v-if="v.nr_recibo_anterior" class="ref mono">
                  referencia: {{ v.nr_recibo_anterior }}
                </div>
                <div class="data">{{ fmtData(v.iniciado_em) }}</div>
              </li>
            </ol>
          </section>

          <section>
            <h4>Tentativas registradas ({{ dados.tentativas.length }})</h4>
            <div v-if="!dados.tentativas.length" class="empty">
              Sem tentativas registradas — só a versão original do zip está em
              base. Envios futuros (massa ou individual) aparecerão aqui.
            </div>
            <ul v-else class="tentativas">
              <li v-for="t in dados.tentativas" :key="t.id">
                <div class="t-head">
                  <span class="seq mono">v{{ t.sequencia }}</span>
                  <span :class="['badge', statusBadge(t.status)]">{{
                    t.status
                  }}</span>
                  <span class="data">{{ fmtData(t.criado_em) }}</span>
                </div>
                <div v-if="t.erro_codigo" class="erro">
                  {{ t.erro_codigo }} — {{ t.erro_mensagem }}
                </div>
                <div class="dl">
                  <a
                    v-if="t.xml_enviado_disponivel"
                    :href="`/explorador-api/api/explorador/tentativa/${t.id}/xml-enviado`"
                    target="_blank"
                    >📤 XML enviado</a
                  >
                  <a
                    v-if="t.xml_retorno_disponivel"
                    :href="`/explorador-api/api/explorador/tentativa/${t.id}/xml-retorno`"
                    target="_blank"
                    >📥 XML retorno</a
                  >
                </div>
              </li>
            </ul>
          </section>
        </div>
      </aside>
    </div>
  </Transition>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 100;
  display: flex;
  justify-content: flex-end;
}
.drawer {
  width: min(540px, 100vw);
  height: 100vh;
  overflow-y: auto;
  padding: 22px 26px 80px;
  border-left: 1px solid rgba(255, 255, 255, 0.08);
}
.drawer-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 18px;
}
.ttl {
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: rgba(240, 209, 229, 0.65);
}
.cpf {
  font-size: 1.3rem;
  font-weight: 700;
  color: #fff;
  margin-top: 2px;
}
.meta {
  font-size: 0.8rem;
  color: rgba(240, 209, 229, 0.7);
  margin-top: 2px;
}
.x {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  color: #fff;
  width: 32px;
  height: 32px;
  cursor: pointer;
  font: inherit;
}
.state {
  padding: 30px 0;
  color: rgba(240, 209, 229, 0.75);
  text-align: center;
}
.state.err {
  color: #ff8a8a;
}
section {
  margin-bottom: 22px;
}
h4 {
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: rgba(240, 209, 229, 0.7);
  margin-bottom: 8px;
}
.versoes {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.versoes li {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 10px 12px;
}
.versoes li.head {
  border-color: rgba(61, 242, 75, 0.4);
  background: rgba(61, 242, 75, 0.06);
}
.v-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.seq {
  font-weight: 700;
  color: #fff;
}
.head-tag {
  background: rgba(61, 242, 75, 0.18);
  color: #6dff7d;
  padding: 1px 6px;
  border-radius: 999px;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.05em;
}
.old-tag {
  background: rgba(255, 255, 255, 0.06);
  color: rgba(240, 209, 229, 0.65);
  padding: 1px 6px;
  border-radius: 999px;
  font-size: 0.65rem;
}
.recibo,
.ref {
  font-size: 0.78rem;
  color: rgba(240, 209, 229, 0.85);
}
.ref {
  color: rgba(240, 209, 229, 0.55);
}
.data {
  font-size: 0.72rem;
  color: rgba(240, 209, 229, 0.55);
  margin-top: 4px;
}

.empty {
  font-size: 0.85rem;
  color: rgba(240, 209, 229, 0.6);
  font-style: italic;
}
.tentativas {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.tentativas li {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 10px 12px;
}
.t-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.badge {
  font-size: 0.68rem;
  padding: 1px 7px;
  border-radius: 999px;
  font-weight: 600;
  letter-spacing: 0.04em;
}
.badge.ok {
  background: rgba(61, 242, 75, 0.18);
  color: #6dff7d;
}
.badge.err {
  background: rgba(255, 90, 90, 0.18);
  color: #ff8a8a;
}
.badge.warn {
  background: rgba(255, 200, 80, 0.18);
  color: #ffc966;
}
.badge.info {
  background: rgba(140, 180, 255, 0.18);
  color: #8cb4ff;
}
.erro {
  margin-top: 6px;
  font-size: 0.78rem;
  color: #ff8a8a;
}
.dl {
  margin-top: 8px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.dl a {
  font-size: 0.78rem;
  color: #c697ff;
  text-decoration: none;
  border: 1px solid rgba(198, 151, 255, 0.3);
  padding: 4px 10px;
  border-radius: 8px;
}
.dl a:hover {
  background: rgba(198, 151, 255, 0.08);
}

.mono {
  font-family: ui-monospace, "Cascadia Code", monospace;
}

.drawer-enter-active,
.drawer-leave-active {
  transition:
    transform 220ms ease,
    opacity 220ms ease;
}
.drawer-enter-from,
.drawer-leave-to {
  transform: translateX(40px);
  opacity: 0;
}
</style>
