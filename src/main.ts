import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import router from "./router";
import { downloadXmlTentativa } from "./services/exploradorApi";
import { useEmpresaStore } from "./stores/empresa";
import "@fontsource-variable/jetbrains-mono";
import "./styles/main.css";
import "./styles/data-table.css";

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.mount("#app");

document.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof Element)) return;

  const anchor = target.closest<HTMLAnchorElement>(
    'a[href*="/api/explorador/tentativa/"]',
  );
  if (!anchor) return;

  const url = new URL(anchor.href, window.location.origin);
  const match = url.pathname.match(
    /\/api\/explorador\/tentativa\/(\d+)\/(xml-enviado|xml-retorno)$/,
  );
  if (!match) return;

  const empresaId = useEmpresaStore().currentId;
  if (!empresaId) return;

  event.preventDefault();
  const itemId = Number(match[1]);
  const tipo = match[2] === "xml-enviado" ? "enviado" : "retorno";
  void downloadXmlTentativa(itemId, empresaId, tipo);
});
