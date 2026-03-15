/**
 * Vue Router configuration.
 *
 * Uses HTML5 history mode. All routes are lazy-loaded for optimal initial
 * bundle size. Auth guard redirects unauthenticated users to /login.
 */

import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: 'Sign In', public: true },
  },
  {
    path: '/auth/oidc/callback',
    name: 'oidc-callback',
    component: () => import('@/views/OidcCallbackView.vue'),
    meta: { title: 'SSO Login', public: true },
  },
  {
    path: '/',
    redirect: '/dashboard',
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { title: 'Dashboard' },
  },
  {
    path: '/groups',
    name: 'groups',
    component: () => import('@/views/GroupsView.vue'),
    meta: { title: 'Groups' },
  },
  {
    path: '/fingerprints',
    name: 'fingerprints',
    component: () => import('@/views/FingerprintEditorView.vue'),
    meta: { title: 'Fingerprint Editor' },
  },
  {
    // Must be before /:groupId to prevent "proposals" being captured as a param
    path: '/fingerprints/proposals',
    name: 'fingerprint-proposals',
    component: () => import('@/views/FingerprintProposalsView.vue'),
    meta: { title: 'Fingerprint Proposals' },
  },
  {
    path: '/fingerprints/:groupId',
    name: 'fingerprint-editor',
    component: () => import('@/views/FingerprintEditorView.vue'),
    meta: { title: 'Fingerprint Editor' },
  },
  {
    path: '/classification',
    name: 'classification',
    component: () => import('@/views/ClassificationView.vue'),
    meta: { title: 'Classification' },
  },
  {
    path: '/anomalies',
    name: 'anomalies',
    component: () => import('@/views/AnomaliesView.vue'),
    meta: { title: 'Anomalies' },
  },
  {
    path: '/agents/:agentId',
    name: 'agent-detail',
    component: () => import('@/views/AgentDetailView.vue'),
    meta: { title: 'Agent Detail' },
  },
  {
    path: '/apps',
    name: 'apps',
    component: () => import('@/views/AppsOverviewView.vue'),
    meta: { title: 'Applications' },
  },
  {
    // :normalizedName may contain slashes (e.g. "foo/bar"), so use (.*) to capture all
    path: '/apps/:normalizedName(.*)',
    name: 'app-detail',
    component: () => import('@/views/AppDetailView.vue'),
    meta: { title: 'App Detail' },
  },
  {
    path: '/taxonomy',
    name: 'taxonomy',
    component: () => import('@/views/TaxonomyView.vue'),
    meta: { title: 'Software Taxonomy' },
  },
  {
    path: '/tags',
    name: 'tags',
    component: () => import('@/views/TagEditorView.vue'),
    meta: { title: 'Tag Rules' },
  },
  {
    path: '/tags/:ruleId',
    name: 'tag-editor',
    component: () => import('@/views/TagEditorView.vue'),
    meta: { title: 'Tag Editor' },
  },
  {
    path: '/sync',
    name: 'sync',
    component: () => import('@/views/SyncView.vue'),
    meta: { title: 'Sync' },
  },
  {
    path: '/users',
    name: 'users',
    component: () => import('@/views/UsersView.vue'),
    meta: { title: 'User Management', roles: ['admin', 'super_admin'] },
  },
  {
    path: '/account/security',
    name: 'account-security',
    component: () => import('@/views/SessionsView.vue'),
    meta: { title: 'Account Security' },
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { title: 'Settings', roles: ['admin', 'super_admin'] },
  },
  {
    path: '/api-keys',
    name: 'api-keys',
    component: () => import('@/views/ApiKeysView.vue'),
    meta: { title: 'API Keys', roles: ['admin', 'super_admin'] },
  },
  {
    path: '/webhooks',
    name: 'webhooks',
    component: () => import('@/views/WebhooksView.vue'),
    meta: { title: 'Webhooks', roles: ['admin', 'super_admin'] },
  },
  {
    path: '/audit',
    name: 'audit',
    component: () => import('@/views/AuditView.vue'),
    meta: { title: 'Audit Log' },
  },
  {
    path: '/audit/chain',
    name: 'audit-chain',
    component: () => import('@/views/AuditChainView.vue'),
    meta: { title: 'Audit Chain', roles: ['analyst', 'admin', 'super_admin'] },
  },
  {
    path: '/tenants',
    name: 'tenants',
    component: () => import('@/views/TenantManagementView.vue'),
    meta: { title: 'Tenant Management', roles: ['super_admin'] },
  },
  {
    path: '/compliance',
    name: 'compliance',
    component: () => import('@/views/ComplianceDashboardView.vue'),
    meta: { title: 'Compliance', roles: ['admin', 'super_admin', 'analyst', 'viewer'] },
  },
  {
    path: '/compliance/platform',
    name: 'platform-compliance',
    component: () => import('@/views/PlatformComplianceView.vue'),
    meta: { title: 'Platform Compliance', roles: ['admin', 'super_admin'] },
  },
  {
    path: '/compliance/settings',
    name: 'compliance-settings',
    component: () => import('@/views/ComplianceSettingsView.vue'),
    meta: { title: 'Compliance Settings', roles: ['admin', 'super_admin'] },
  },
  {
    path: '/compliance/control/:controlId',
    name: 'compliance-control',
    component: () => import('@/views/ComplianceControlView.vue'),
    meta: { title: 'Control Detail', roles: ['admin', 'super_admin', 'analyst', 'viewer'] },
  },
  {
    path: '/enforcement',
    name: 'enforcement',
    component: () => import('@/views/EnforcementView.vue'),
    meta: { title: 'Enforcement Rules', roles: ['admin', 'super_admin', 'analyst', 'viewer'] },
  },
  {
    path: '/guide',
    name: 'guide',
    component: () => import('@/views/GettingStartedView.vue'),
    meta: { title: 'Getting Started' },
  },
  {
    path: '/library',
    name: 'library',
    component: () => import('@/views/LibraryBrowserView.vue'),
    meta: { title: 'Fingerprint Library' },
  },
  {
    // Must be before /library/:entryId to prevent "sources" being captured as a param
    path: '/library/sources',
    name: 'library-sources',
    component: () => import('@/views/LibrarySourcesView.vue'),
    meta: { title: 'Library Sources' },
  },
  {
    path: '/library/:entryId',
    name: 'library-entry',
    component: () => import('@/views/LibraryEntryView.vue'),
    meta: { title: 'Library Entry' },
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

/** Auth guard — redirect to /login if not authenticated. */
router.beforeEach(async (to) => {
  if (to.meta.public) return true

  // Lazy-import to avoid circular deps (store uses router indirectly)
  const { useAuthStore } = await import('@/stores/useAuthStore')
  const auth = useAuthStore()

  // Initialize once (validates stored token)
  await auth.init()

  if (!auth.isAuthenticated) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  // Role-based access control: redirect unauthorized users to dashboard
  const requiredRoles = to.meta.roles as string[] | undefined
  if (requiredRoles && auth.user) {
    if (!requiredRoles.includes(auth.user.role)) {
      return '/dashboard'
    }
  }

  return true
})

/** Update the document title on each navigation. */
router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} — Sentora` : 'Sentora'
})

export default router
