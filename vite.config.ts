import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5174,
    strictPort: true,
    // Proxy reverso pro backend V2 unificado (FastAPI local)
    // Frontend chama sempre /api/... → same-origin, CSP fica simples
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        // uploads grandes (XLSX dominio, ZIPs eSocial) — sem timeout
        timeout: 0,
        proxyTimeout: 0,
      },
      // LEGACY V1 — manter ate frontend ser totalmente migrado
      "/py-api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/py-api/, ""),
      },
      "/explorador-api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/explorador-api/, ""),
        timeout: 0,
        proxyTimeout: 0,
      },
    },
  },
  build: {
    target: "esnext",
    sourcemap: false, // não vazar source em produção
    rollupOptions: {
      output: {
        manualChunks: {
          vue: ["vue", "vue-router", "pinia"],
        },
      },
    },
  },
});
