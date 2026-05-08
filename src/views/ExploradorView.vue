<script setup lang="ts">
import { ref, onMounted } from "vue";
import { listarZips, type ZipRow } from "@/services/exploradorApi";
import ZipUploader from "@/components/explorador/ZipUploader.vue";
import ZipsList from "@/components/explorador/ZipsList.vue";
import EventosViewer from "@/components/explorador/EventosViewer.vue";
import HistoricoAtividade from "@/components/explorador/HistoricoAtividade.vue";
import ChainWalkPanel from "@/components/explorador/timeline/ChainWalkPanel.vue";

// MVP: empresa fixa = SOLUCOES (id=1)
const empresaId = 1;

const zips = ref<ZipRow[]>([]);
const carregando = ref(true);
const erro = ref<string | null>(null);
const historicoRef = ref<InstanceType<typeof HistoricoAtividade> | null>(null);

const zipVisualizando = ref<ZipRow | null>(null);

async function carregar() {
  carregando.value = true;
  erro.value = null;
  try {
    const r = await listarZips(empresaId);
    zips.value = r.items;
    historicoRef.value?.carregar();
  } catch (e) {
    erro.value =
      "Não foi possível carregar os ZIPs do Explorador. Tente novamente em instantes.";
  } finally {
    carregando.value = false;
  }
}

onMounted(carregar);

function onUploaded(zip: ZipRow) {
  // injeta no topo (ou substitui se já existir por sha)
  const idx = zips.value.findIndex((z) => z.id === zip.id);
  if (idx >= 0) zips.value[idx] = zip;
  else zips.value.unshift(zip);
  historicoRef.value?.carregar();
}

function abrirVisualizacao(z: ZipRow) {
  zipVisualizando.value = z;
}

function fecharVisualizacao() {
  zipVisualizando.value = null;
}
</script>

<template>
  <div class="explorador">
    <!-- Modo visualização (sobre o resto) -->
    <template v-if="zipVisualizando">
      <EventosViewer :zip="zipVisualizando" @fechar="fecharVisualizacao" />
    </template>

    <template v-else>
      <header class="page-head">
        <div>
          <h1 class="title gg-glow">Explorador de Arquivos</h1>
          <p class="subtitle">
            Suba os zips de retorno do eSocial. Eles ficam guardados, indexados
            por evento e CPF, e podem ser explorados visualmente.
          </p>
        </div>
        <div class="empresa-pill">
          <span class="dot"></span>
          <span>SOLUCOES</span>
        </div>
      </header>

      <section class="upload-section">
        <h2 class="section-title">Enviar zip</h2>
        <ZipUploader :empresa-id="empresaId" @uploaded="onUploaded" />
      </section>

      <section class="lista-section">
        <div class="sec-head">
          <h2 class="section-title">Zips enviados</h2>
          <button class="btn-refresh" :disabled="carregando" @click="carregar">
            ↻ atualizar
          </button>
        </div>

        <div v-if="erro" class="erro">⚠ {{ erro }}</div>

        <div v-if="carregando && zips.length === 0" class="loading">
          <div class="spinner"></div>
          carregando…
        </div>

        <ZipsList
          v-else
          :zips="zips"
          @visualizar="abrirVisualizacao"
          @refresh="carregar"
        />
      </section>

      <section class="hist-section">
        <ChainWalkPanel :empresa-id="empresaId" />
      </section>

      <section class="hist-section">
        <HistoricoAtividade :empresa-id="empresaId" ref="historicoRef" />
      </section>
    </template>
  </div>
</template>

<style scoped>
.explorador {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 26px;
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  flex-wrap: wrap;
}
.title {
  font-size: 2rem;
  font-weight: 800;
  color: #fff;
  margin: 0;
  letter-spacing: -0.02em;
}
.subtitle {
  margin: 6px 0 0;
  color: rgba(240, 209, 229, 0.7);
  font-size: 0.95rem;
  max-width: 720px;
}

.empresa-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 14px;
  background: rgba(61, 242, 75, 0.08);
  border: 1px solid rgba(61, 242, 75, 0.35);
  border-radius: 999px;
  color: #fff;
  font-weight: 600;
  font-size: 0.85rem;
}
.empresa-pill .dot {
  width: 8px;
  height: 8px;
  background: #3df24b;
  border-radius: 50%;
  box-shadow: 0 0 8px #3df24b;
  animation: pulse 1.6s ease-in-out infinite;
}
@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}

.section-title {
  font-size: 1.05rem;
  font-weight: 700;
  color: #fff;
  margin: 0 0 12px;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  font-size: 0.85rem;
  color: rgba(240, 209, 229, 0.65);
  letter-spacing: 0.08em;
}

.sec-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.sec-head .section-title {
  margin: 0;
}

.btn-refresh {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(240, 209, 229, 0.2);
  color: #fff;
  border-radius: 8px;
  padding: 6px 12px;
  cursor: pointer;
  font: inherit;
  font-size: 0.85rem;
}
.btn-refresh:hover:not(:disabled) {
  border-color: rgba(61, 242, 75, 0.5);
}
.btn-refresh:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.loading {
  text-align: center;
  padding: 30px;
  color: rgba(240, 209, 229, 0.7);
}
.spinner {
  width: 36px;
  height: 36px;
  border: 3px solid rgba(61, 242, 75, 0.15);
  border-top-color: #3df24b;
  border-radius: 50%;
  margin: 0 auto 10px;
  animation: spin 900ms linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.erro {
  background: rgba(255, 80, 80, 0.08);
  border: 1px solid rgba(255, 80, 80, 0.3);
  color: #ffb3b3;
  border-radius: 10px;
  padding: 12px 14px;
  font-size: 0.9rem;
}
</style>
