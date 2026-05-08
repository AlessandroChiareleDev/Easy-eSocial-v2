<script setup lang="ts">
import { ref, watch, onMounted } from "vue";
import {
  listarEventos,
  urlXmlEvento,
  type EventoRow,
} from "@/services/exploradorApi";

const props = defineProps<{
  empresaId: number;
  zipId: number;
  tipoEvento: string;
}>();

const loading = ref(true);
const erro = ref<string | null>(null);
const items = ref<EventoRow[]>([]);
const total = ref(0);
const offset = ref(0);
const limit = 100;
const filtroCpf = ref("");

async function carregar(reset = false) {
  loading.value = true;
  erro.value = null;
  if (reset) {
    offset.value = 0;
    items.value = [];
  }
  try {
    const r = await listarEventos({
      empresaId: props.empresaId,
      zipId: props.zipId,
      tipoEvento: props.tipoEvento,
      ...(filtroCpf.value ? { cpf: filtroCpf.value } : {}),
      limit,
      offset: offset.value,
    });
    if (reset) items.value = r.items;
    else items.value.push(...r.items);
    total.value = r.total;
  } catch (e) {
    erro.value = (e as Error).message;
  } finally {
    loading.value = false;
  }
}

function carregarMais() {
  offset.value += limit;
  carregar(false);
}

onMounted(() => carregar(true));
watch(
  () => props.tipoEvento,
  () => carregar(true),
);

let debounce: number | null = null;
watch(filtroCpf, () => {
  if (debounce) clearTimeout(debounce);
  debounce = window.setTimeout(() => carregar(true), 250);
});
</script>

<template>
  <div class="lista">
    <div class="toolbar">
      <input
        v-model="filtroCpf"
        type="text"
        inputmode="numeric"
        maxlength="11"
        placeholder="filtrar por CPF…"
        class="input"
      />
      <div class="counter">
        <span class="n">{{ total.toLocaleString("pt-BR") }}</span>
        <span class="l">eventos</span>
      </div>
    </div>

    <div v-if="erro" class="erro">⚠ {{ erro }}</div>

    <div class="table-wrap liquid-glass">
      <table>
        <thead>
          <tr>
            <th>CPF</th>
            <th>Período</th>
            <th>id_evento</th>
            <th>nº recibo</th>
            <th>arquivo</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="ev in items" :key="ev.id">
            <td class="mono">{{ ev.cpf ?? "—" }}</td>
            <td class="mono">{{ ev.per_apur ?? "—" }}</td>
            <td class="mono small">{{ ev.id_evento ?? "—" }}</td>
            <td class="mono small">{{ ev.nr_recibo ?? "—" }}</td>
            <td class="mono small ellipsis" :title="ev.xml_entry_name">
              {{ ev.xml_entry_name }}
            </td>
            <td>
              <a
                class="btn-xml"
                :href="urlXmlEvento(ev.id)"
                target="_blank"
                rel="noopener"
                >XML</a
              >
            </td>
          </tr>
          <tr v-if="!loading && items.length === 0">
            <td colspan="6" class="empty">Nenhum evento encontrado.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="footer">
      <button
        v-if="items.length < total"
        class="btn-ghost"
        :disabled="loading"
        @click="carregarMais"
      >
        {{
          loading ? "carregando…" : `carregar mais (${items.length} / ${total})`
        }}
      </button>
      <span v-else-if="!loading && items.length > 0" class="muted">
        Todos os {{ total }} eventos carregados.
      </span>
      <span v-if="loading && items.length === 0" class="muted"
        >carregando…</span
      >
    </div>
  </div>
</template>

<style scoped>
.lista {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 14px;
}
.input {
  flex: 1;
  max-width: 320px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(240, 209, 229, 0.18);
  border-radius: 8px;
  padding: 9px 12px;
  color: #fff;
  font: inherit;
}
.input:focus {
  outline: none;
  border-color: rgba(61, 242, 75, 0.6);
}
.counter {
  margin-left: auto;
  text-align: right;
}
.counter .n {
  font-size: 1.2rem;
  font-weight: 700;
  color: #3df24b;
  text-shadow: 0 0 10px rgba(61, 242, 75, 0.4);
  font-variant-numeric: tabular-nums;
}
.counter .l {
  font-size: 0.7rem;
  color: rgba(240, 209, 229, 0.6);
  text-transform: uppercase;
  margin-left: 6px;
  letter-spacing: 0.06em;
}

.table-wrap {
  border-radius: 12px;
  overflow: hidden;
  padding: 0;
}
table {
  width: 100%;
  border-collapse: collapse;
}
thead th {
  background: rgba(61, 242, 75, 0.06);
  color: rgba(240, 209, 229, 0.85);
  text-align: left;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(240, 209, 229, 0.1);
}
tbody td {
  padding: 8px 12px;
  border-bottom: 1px solid rgba(240, 209, 229, 0.05);
  color: #fff;
  font-size: 0.88rem;
}
tbody tr:hover {
  background: rgba(61, 242, 75, 0.04);
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-variant-numeric: tabular-nums;
}
.small {
  font-size: 0.78rem;
  color: rgba(240, 209, 229, 0.8);
}
.ellipsis {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.empty {
  text-align: center;
  padding: 28px;
  color: rgba(240, 209, 229, 0.6);
}
.btn-xml {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 6px;
  background: rgba(61, 242, 75, 0.12);
  border: 1px solid rgba(61, 242, 75, 0.4);
  color: #3df24b;
  text-decoration: none;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}
.btn-xml:hover {
  background: rgba(61, 242, 75, 0.22);
}
.footer {
  text-align: center;
  padding: 8px;
}
.btn-ghost {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(240, 209, 229, 0.2);
  color: #fff;
  border-radius: 8px;
  padding: 8px 16px;
  cursor: pointer;
  font: inherit;
}
.btn-ghost:hover:not(:disabled) {
  border-color: rgba(61, 242, 75, 0.5);
}
.muted {
  color: rgba(240, 209, 229, 0.55);
  font-size: 0.85rem;
}
.erro {
  background: rgba(255, 80, 80, 0.08);
  border: 1px solid rgba(255, 80, 80, 0.3);
  color: #ffb3b3;
  border-radius: 8px;
  padding: 10px;
  font-size: 0.9rem;
}
</style>
