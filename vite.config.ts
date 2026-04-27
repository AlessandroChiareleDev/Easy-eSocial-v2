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
    // Proxy reverso pro backend Node antigo (Express :3333)
    // Frontend chama sempre /api/... → same-origin, CSP fica simples
    proxy: {
      "/api": {
        target: "http://localhost:3333",
        changeOrigin: true,
      },
      // Backend Python (FastAPI) — serve TUDO de eSocial S-1010/S-1210
      "/py-api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/py-api/, ""),
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
