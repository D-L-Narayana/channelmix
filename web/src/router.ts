import { createRouter, createWebHistory, type RouteLocationNormalized } from 'vue-router'
import { useWorkspaceStore } from './stores/workspace'

export const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: (_to, _from, saved) => saved ?? { top: 0 },
  routes: [
    { path: '/', name: 'home', component: () => import('./pages/LandingPage.vue'), meta: { title: 'ChannelMix' } },
    {
      path: '/w/:slug',
      component: () => import('./components/AppShell.vue'),
      props: true,
      children: [
        { path: '', name: 'dashboard', component: () => import('./pages/DashboardPage.vue'), meta: { title: 'Dashboard' } },
        { path: 'import', name: 'import', component: () => import('./pages/ImportPage.vue'), meta: { title: 'Import data' } },
        { path: 'campaigns/:id', name: 'campaign', component: () => import('./pages/CampaignPage.vue'), meta: { title: 'Campaign' } },
        { path: 'settings', name: 'settings', component: () => import('./pages/SettingsPage.vue'), meta: { title: 'Settings' } },
      ],
    },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('./pages/NotFoundPage.vue'), meta: { title: 'Not found' } },
  ],
})

/** Magic link `/w/<slug>?key=...` -> store key, strip it from the URL, open the workspace. */
router.beforeEach(async (to: RouteLocationNormalized) => {
  const slug = typeof to.params.slug === 'string' ? to.params.slug : null
  if (!slug) return true
  const ws = useWorkspaceStore()
  const urlKey = typeof to.query.key === 'string' ? to.query.key : null
  // don't block navigation on the network; AppShell renders loading/invalid/unreachable states
  void ws.open(slug, urlKey)
  if (urlKey) {
    const q = { ...to.query }
    delete q.key
    return { ...to, query: q, replace: true }
  }
  return true
})

router.afterEach((to) => {
  const t = to.meta.title as string | undefined
  const slug = typeof to.params.slug === 'string' ? to.params.slug : null
  document.title = t && t !== 'ChannelMix' ? `${t} · ${slug ? slug + ' · ' : ''}ChannelMix` : 'ChannelMix — cross-channel ad spend, live'
})
