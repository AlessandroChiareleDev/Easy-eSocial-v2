import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import router from "./router";
import "@fontsource-variable/jetbrains-mono";
import "./styles/main.css";
import "./styles/data-table.css";

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.mount("#app");
