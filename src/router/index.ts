import {
  createRouter,
  createWebHistory,
  type RouteRecordRaw,
} from "vue-router";
import { useAuthStore } from "@/stores/auth";

/**
 * Easy-Social V2 — rotas
 *  /login  → tela de entrada (pública)
 *  /       → AppLayout (topbar + bg) → 6 views protegidas
 */
const routes: RouteRecordRaw[] = [
  {
    path: "/login",
    name: "login",
    component: () => import("@/views/LoginView.vue"),
    meta: { title: "Entrar", public: true },
  },
  {
    path: "/",
    component: () => import("@/layouts/AppLayout.vue"),
    children: [
      {
        path: "",
        name: "painel",
        component: () => import("@/views/PainelView.vue"),
        meta: { title: "Painel" },
      },
      {
        path: "tabelas",
        name: "tabelas",
        component: () => import("@/views/TabelasView.vue"),
        meta: { title: "Tabelas" },
      },
      {
        path: "tabelas/:nome",
        name: "tabela-detail",
        component: () => import("@/views/TabelaDetailView.vue"),
        meta: { title: "Tabela" },
      },
      {
        path: "esocial/s1010",
        name: "s1010",
        component: () => import("@/views/S1010View.vue"),
        meta: { title: "eSocial S-1010" },
      },
      {
        path: "esocial/s1210-anual",
        name: "s1210-anual",
        component: () => import("@/views/S1210AnualView.vue"),
        meta: { title: "S-1210 Anual" },
      },
      {
        path: "logs",
        name: "logs",
        component: () => import("@/views/LogsView.vue"),
        meta: { title: "Logs de Sistema" },
      },
      {
        path: "problemas",
        name: "problemas",
        component: () => import("@/views/ProblemasView.vue"),
        meta: { title: "Problemas" },
      },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (!to.meta?.public && !auth.isAuthenticated) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (to.name === "login" && auth.isAuthenticated) {
    return { path: "/" };
  }
});

router.afterEach((to) => {
  const base = (import.meta.env.VITE_APP_NAME as string) || "Easy-Social";
  const title = to.meta?.title as string | undefined;
  document.title = title ? `${title} · ${base}` : base;
});

export default router;
