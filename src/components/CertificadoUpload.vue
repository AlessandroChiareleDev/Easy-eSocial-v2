<script setup lang="ts">
/**
 * F9.7 — CertificadoUpload
 *
 * Upload de certificado A1 (.pfx/.p12) com senha. Backend:
 * POST /api/certificados/upload (multipart: file, senha)
 *
 * Emit `uploaded` em sucesso pra o pai recarregar a lista.
 */
import { ref } from "vue";
import { api } from "@/services/api";

const emit = defineEmits<{ uploaded: [] }>();

const file = ref<File | null>(null);
const senha = ref("");
const showSenha = ref(false);
const loading = ref(false);
const erro = ref<string | null>(null);
const ok = ref<string | null>(null);

interface UploadOk {
  id: number;
  cnpj: string;
  titular: string;
  validade: string;
}

function onPick(e: Event) {
  const input = e.target as HTMLInputElement;
  const f = input.files?.[0] ?? null;
  if (f && !/\.(pfx|p12)$/i.test(f.name)) {
    erro.value = "Arquivo precisa ser .pfx ou .p12";
    file.value = null;
    return;
  }
  erro.value = null;
  file.value = f;
}

async function submit() {
  if (!file.value) {
    erro.value = "Escolha um arquivo .pfx/.p12";
    return;
  }
  if (!senha.value) {
    erro.value = "Senha do certificado é obrigatória";
    return;
  }
  loading.value = true;
  erro.value = null;
  ok.value = null;
  try {
    const fd = new FormData();
    fd.append("file", file.value);
    fd.append("senha", senha.value);
    const res = await api.post<UploadOk>("/certificados/upload", fd);
    ok.value = `Certificado de ${res.titular} aceito (válido até ${new Date(res.validade).toLocaleDateString("pt-BR")}).`;
    file.value = null;
    senha.value = "";
    const fileInput = document.getElementById("cert-file") as HTMLInputElement | null;
    if (fileInput) fileInput.value = "";
    emit("uploaded");
  } catch (e) {
    erro.value = e instanceof Error ? e.message : "Falha ao enviar";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <form class="cert-upload" @submit.prevent="submit" novalidate>
    <h3 class="title">Enviar novo certificado A1</h3>

    <div class="field">
      <label for="cert-file">Arquivo (.pfx ou .p12)</label>
      <input
        id="cert-file"
        type="file"
        accept=".pfx,.p12"
        :disabled="loading"
        @change="onPick"
      />
      <p v-if="file" class="hint">
        {{ file.name }} · {{ Math.round(file.size / 1024) }} KB
      </p>
    </div>

    <div class="field">
      <label for="cert-senha">Senha do certificado</label>
      <div class="pwd-wrap">
        <input
          id="cert-senha"
          v-model="senha"
          :type="showSenha ? 'text' : 'password'"
          autocomplete="off"
          :disabled="loading"
          placeholder="senha do .pfx"
        />
        <button
          type="button"
          class="pwd-toggle"
          @click="showSenha = !showSenha"
          :aria-label="showSenha ? 'Ocultar' : 'Mostrar'"
        >
          {{ showSenha ? "ocultar" : "mostrar" }}
        </button>
      </div>
      <p class="hint warn">
        A senha é cifrada no servidor antes de gravar. Nunca sai em logs.
      </p>
    </div>

    <div v-if="erro" class="banner err">{{ erro }}</div>
    <div v-if="ok" class="banner ok">{{ ok }}</div>

    <button type="submit" class="submit" :disabled="loading || !file">
      {{ loading ? "Validando…" : "Enviar certificado" }}
    </button>
  </form>
</template>

<style scoped>
.cert-upload {
  display: flex;
  flex-direction: column;
  gap: 18px;
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 14px;
  padding: 24px;
  color: #e6e9f2;
}
.title {
  margin: 0;
  font-size: 1.1rem;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.field label {
  font-size: 0.85rem;
  color: #cbd5e1;
}
.field input[type="file"],
.field input[type="text"],
.field input[type="password"] {
  padding: 10px 12px;
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 8px;
  color: #e6e9f2;
  font: inherit;
}
.pwd-wrap {
  display: flex;
  gap: 8px;
}
.pwd-wrap input {
  flex: 1;
}
.pwd-toggle {
  background: rgba(96, 165, 250, 0.15);
  color: #93c5fd;
  border: 1px solid rgba(96, 165, 250, 0.3);
  border-radius: 8px;
  padding: 0 12px;
  cursor: pointer;
  font-size: 0.8rem;
}
.hint {
  margin: 0;
  font-size: 0.8rem;
  color: #94a3b8;
}
.hint.warn {
  color: #fbbf24;
}
.banner {
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 0.9rem;
}
.banner.err {
  background: rgba(248, 113, 113, 0.15);
  color: #fca5a5;
  border: 1px solid rgba(248, 113, 113, 0.3);
}
.banner.ok {
  background: rgba(34, 197, 94, 0.15);
  color: #86efac;
  border: 1px solid rgba(34, 197, 94, 0.3);
}
.submit {
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  color: white;
  border: none;
  padding: 12px;
  border-radius: 10px;
  font-weight: 600;
  cursor: pointer;
  font-size: 0.95rem;
}
.submit:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
