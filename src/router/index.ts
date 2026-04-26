import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router';

/**
 * Easy-Social V2 — 6 telas confirmadas:
 *  1. Painel        (home, cérebro operacional)
 *  2. Tabelas
 *  3. eSocial S-1010
 *  4. S-1210 Anual
 *  5. Logs de Sistema
 *  6. Problemas
 */
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'painel',
    component: () => import('@/views/PainelView.vue'),
    meta: { title: 'Painel' },
  },
  {
    path: '/tabelas',
    name: 'tabelas',
    component: () => import('@/views/TabelasView.vue'),
    meta: { title: 'Tabelas' },
  },
  {
    path: '/esocial/s1010',
    name: 's1010',
    component: () => import('@/views/S1010View.vue'),
    meta: { title: 'eSocial S-1010' },
  },
  {
    path: '/esocial/s1210-anual',
    name: 's1210-anual',
    component: () => import('@/views/S1210AnualView.vue'),
    meta: { title: 'S-1210 Anual' },
  },
  {
    path: '/logs',
    name: 'logs',
    component: () => import('@/views/LogsView.vue'),
    meta: { title: 'Logs de Sistema' },
  },
  {
    path: '/problemas',
    name: 'problemas',
    component: () => import('@/views/ProblemasView.vue'),
    meta: { title: 'Problemas' },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.afterEach((to) => {
  const base = (import.meta.env.VITE_APP_NAME as string) || 'Easy-Social';
  const title = to.meta?.title as string | undefined;
  document.title = title ? `${title} · ${base}` : base;
});

export default router;
