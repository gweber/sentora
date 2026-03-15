<!--
  Root shell: collapsible sidebar + topbar + scrollable main content.
  LoginView renders full-screen without the shell.
-->
<script setup lang="ts">
import { computed, watch, nextTick, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSyncStore } from '@/stores/useSyncStore'
import { useAuthStore } from '@/stores/useAuthStore'
import { useComplianceStore } from '@/stores/useComplianceStore'
import { useEnforcementStore } from '@/stores/useEnforcementStore'
import { useBranding } from '@/composables/useBranding'
import { useToast } from '@/composables/useToast'

const toast = useToast()
const complianceStore = useComplianceStore()
const enforcementStore = useEnforcementStore()

/** Total violations across compliance + enforcement for sidebar badge. */
const totalViolationCount = computed(() =>
  (complianceStore.dashboard?.total_violations ?? 0)
  + (enforcementStore.summary?.total_violations ?? 0),
)
import { useDeployment } from '@/composables/useDeployment'
import * as tenantApi from '@/api/tenants'
import type { Tenant } from '@/api/tenants'

const route = useRoute()
const router = useRouter()
const mainRef = ref<HTMLElement | null>(null)
const syncStore = useSyncStore()
const auth = useAuthStore()
const { brandName, brandTagline, brandLogoUrl, loadBranding } = useBranding()
const { isOnprem, isSaas, loadDeploymentInfo } = useDeployment()

// Tenant switcher state (super_admin only)
const tenants = ref<Tenant[]>([])
const activeTenantSlug = ref<string | null>(localStorage.getItem('sentora_tenant'))
const tenantDropdownOpen = ref(false)

async function loadTenants() {
  if (!auth.isSuperAdmin) return
  try {
    const resp = await tenantApi.listTenants()
    tenants.value = resp.tenants.filter(t => !t.disabled)
  } catch {
    // Tenants may not be enabled — silently ignore
  }
}

function switchTenant(slug: string | null) {
  activeTenantSlug.value = slug
  tenantDropdownOpen.value = false
  if (slug) {
    localStorage.setItem('sentora_tenant', slug)
  } else {
    localStorage.removeItem('sentora_tenant')
  }
  // Reload to apply tenant context
  window.location.reload()
}

const activeTenantName = computed(() => {
  if (!activeTenantSlug.value) return 'Default'
  return tenants.value.find(t => t.slug === activeTenantSlug.value)?.name ?? activeTenantSlug.value
})

onMounted(() => {
  loadBranding()
  loadDeploymentInfo()
  loadTenants()
})

// Sidebar collapse
const collapsed = ref(localStorage.getItem('sidebar_collapsed') === 'true')
function toggleSidebar() {
  collapsed.value = !collapsed.value
  localStorage.setItem('sidebar_collapsed', String(collapsed.value))
}

// Focus main on route change
watch(() => route.path, () => {
  nextTick(() => { mainRef.value?.focus() })
})

// Don't show shell on login page
const showShell = computed(() => route.name !== 'login')

const nav = [
  { label: 'Dashboard',          path: '/dashboard',              icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
  { label: 'Groups',             path: '/groups',                 icon: 'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10' },
  { label: 'Applications',       path: '/apps',                   icon: 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4' },
  { label: 'Taxonomy',           path: '/taxonomy',               icon: 'M4 6h16M4 10h16M4 14h16M4 18h16' },
  { label: 'Tag Rules',          path: '/tags',                   icon: 'M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z' },
  { label: 'Fingerprint Editor', path: '/fingerprints',           icon: 'M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18' },
  { label: 'Proposals',          path: '/fingerprints/proposals', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4' },
  { label: 'Library',            path: '/library',                icon: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253' },
  { label: 'Classification',     path: '/classification',         icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' },
  { label: 'Anomalies',          path: '/anomalies',              icon: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z' },
]

const bottomNav = computed(() => {
  const items = [
    { label: 'Settings',         path: '/settings', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z' },
    { label: 'Sync',             path: '/sync',     icon: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15' },
    { label: 'Audit Log',        path: '/audit',    icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01' },
    { label: 'Getting Started',  path: '/guide',    icon: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253' },
  ]
  // Admin-only pages
  if (auth.isAdmin) {
    items.splice(1, 0, { label: 'Users', path: '/users', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z' })
    items.splice(2, 0, { label: 'Webhooks', path: '/webhooks', icon: 'M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1' })
    items.splice(3, 0, { label: 'API Keys', path: '/api-keys', icon: 'M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z' })
    items.splice(3, 0, { label: 'Compliance', path: '/compliance', icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z' })
    items.splice(4, 0, { label: 'Enforcement', path: '/enforcement', icon: 'M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z' })
  }
  // Library Sources: admin in on-prem, super_admin in SaaS
  if ((isOnprem.value && auth.isAdmin) || auth.isSuperAdmin) {
    items.push({ label: 'Library Sources', path: '/library/sources', icon: 'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4' })
  }
  // Tenants: SaaS only, super_admin only
  if (isSaas.value && auth.isSuperAdmin) {
    items.push({ label: 'Tenants', path: '/tenants', icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4' })
  }
  return items
})

function isActive(path: string) {
  if (path === '/dashboard') return route.path === path
  if (path === '/fingerprints/proposals') return route.path === path || route.path.startsWith(path + '/')
  if (path === '/fingerprints') return route.path === path || (route.path.startsWith(path + '/') && !route.path.startsWith('/fingerprints/proposals'))
  if (path === '/library/sources') return route.path === path || route.path.startsWith(path + '/')
  if (path === '/library') return route.path === path || (route.path.startsWith(path + '/') && !route.path.startsWith('/library/sources'))
  return route.path.startsWith(path)
}

const pageTitle = computed(() => {
  const all = [...nav, ...bottomNav.value]
  return all.find(n => isActive(n.path))?.label ?? 'Sentora'
})
const isSyncing = computed(() => syncStore.currentRun?.status === 'running')

async function handleLogout() {
  try {
    await auth.logout()
  } finally {
    router.push('/login')
  }
}

/** Role badge color. */
const roleBadge = computed(() => {
  switch (auth.user?.role) {
    case 'super_admin': return 'bg-purple-500/20 text-purple-400'
    case 'admin': return 'bg-red-500/20 text-red-400'
    case 'analyst': return 'bg-amber-500/20 text-amber-400'
    default: return 'bg-slate-500/20 text-slate-400'
  }
})
</script>

<template>
  <!-- Login page — full-screen, no shell -->
  <router-view v-if="!showShell" />

  <!-- App shell -->
  <div v-else class="flex h-screen overflow-hidden">

    <!-- Skip to content -->
    <a
      href="#main-content"
      class="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:top-2 focus:left-2 focus:px-4 focus:py-2 focus:bg-indigo-600 focus:text-white focus:rounded focus:font-semibold focus:text-sm"
    >Skip to main content</a>

    <!-- ── Sidebar ── -->
    <aside
      class="relative flex flex-col shrink-0 bg-[#0c111d] border-r border-white/[0.06] transition-[width] duration-200"
      :class="collapsed ? 'w-16' : 'w-60'"
      aria-label="Main navigation"
    >

      <!-- Brand + collapse toggle -->
      <div class="flex items-center h-[52px] border-b border-white/[0.06] shrink-0" :class="collapsed ? 'justify-center px-2' : 'gap-3 px-5'">
        <div class="flex items-center justify-center w-7 h-7 rounded-lg shrink-0" style="background: rgba(var(--brand-primary-rgb), 0.2);">
          <img v-if="brandLogoUrl" :src="brandLogoUrl" alt="" class="w-[15px] h-[15px] object-contain" />
          <svg v-else class="w-[15px] h-[15px]" style="color: var(--brand-primary-light);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.2" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
        <div v-if="!collapsed" class="flex-1 min-w-0">
          <p class="text-[13px] font-semibold text-white tracking-[-0.2px] leading-none">{{ brandName }}</p>
          <p class="text-[10px] text-slate-500 mt-0.5 leading-none">{{ brandTagline }}</p>
        </div>
        <button
          v-if="!collapsed"
          @click="toggleSidebar"
          class="p-1 rounded hover:bg-white/[0.06] text-slate-500 hover:text-slate-300 transition"
          aria-label="Collapse sidebar"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
        </button>
      </div>

      <!-- Expand button (collapsed state) -->
      <button
        v-if="collapsed"
        @click="toggleSidebar"
        class="mx-auto mt-2 p-1.5 rounded hover:bg-white/[0.06] text-slate-500 hover:text-slate-300 transition"
        aria-label="Expand sidebar"
      >
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
        </svg>
      </button>

      <!-- Nav links -->
      <nav class="flex-1 overflow-y-auto py-3 space-y-0.5" :class="collapsed ? 'px-1.5' : 'px-2'" role="navigation" aria-label="Primary">
        <router-link
          v-for="item in nav"
          :key="item.path"
          :to="item.path"
          :aria-current="isActive(item.path) ? 'page' : undefined"
          :aria-label="item.label"
          :title="collapsed ? item.label : undefined"
          class="group relative flex items-center rounded-[6px] transition-all duration-100 no-underline"
          :class="[
            collapsed ? 'justify-center py-2.5 px-0' : 'gap-3 px-3 py-[7px]',
            isActive(item.path) ? 'bg-indigo-500/[0.15] text-white' : 'text-slate-400 hover:bg-white/[0.045] hover:text-slate-100'
          ]"
        >
          <span
            v-if="!collapsed"
            class="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-4 rounded-r-full bg-indigo-400 transition-opacity duration-100"
            :class="isActive(item.path) ? 'opacity-100' : 'opacity-0'"
            aria-hidden="true"
          />
          <svg
            class="w-[15px] h-[15px] shrink-0 transition-colors duration-100"
            :class="isActive(item.path) ? 'text-indigo-400' : 'text-slate-500 group-hover:text-slate-300'"
            fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"
            aria-hidden="true"
          >
            <path stroke-linecap="round" stroke-linejoin="round" :d="item.icon" />
          </svg>
          <span v-if="!collapsed" class="text-[13px] font-medium leading-none">{{ item.label }}</span>

          <!-- Anomalies badge -->
          <span
            v-if="item.path === '/anomalies' && syncStore.lastCompletedRun && !collapsed"
            class="ml-auto text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-400"
          >!</span>

          <!-- Violations badge -->
          <span
            v-if="item.path === '/compliance' && totalViolationCount > 0 && !collapsed"
            class="ml-auto text-[10px] font-medium px-1.5 py-0.5 rounded-full"
            style="background: var(--error-bg); color: var(--error-text);"
          >{{ totalViolationCount }}</span>
        </router-link>

        <!-- Divider -->
        <div class="my-1.5 border-t border-white/[0.06]" :class="collapsed ? 'mx-1' : 'mx-2'"></div>

        <!-- Bottom nav -->
        <router-link
          v-for="item in bottomNav"
          :key="item.path"
          :to="item.path"
          :aria-current="isActive(item.path) ? 'page' : undefined"
          :aria-label="item.label"
          :title="collapsed ? item.label : undefined"
          class="group relative flex items-center rounded-[6px] transition-all duration-100 no-underline"
          :class="[
            collapsed ? 'justify-center py-2.5 px-0' : 'gap-3 px-3 py-[7px]',
            isActive(item.path) ? 'bg-indigo-500/[0.15] text-white' : 'text-slate-400 hover:bg-white/[0.045] hover:text-slate-100'
          ]"
        >
          <span
            v-if="!collapsed"
            class="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-4 rounded-r-full bg-indigo-400 transition-opacity duration-100"
            :class="isActive(item.path) ? 'opacity-100' : 'opacity-0'"
            aria-hidden="true"
          />
          <svg
            class="w-[15px] h-[15px] shrink-0 transition-colors duration-100"
            :class="isActive(item.path) ? 'text-indigo-400' : 'text-slate-500 group-hover:text-slate-300'"
            fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"
            aria-hidden="true"
          >
            <path stroke-linecap="round" stroke-linejoin="round" :d="item.icon" />
          </svg>
          <span v-if="!collapsed" class="text-[13px] font-medium leading-none">{{ item.label }}</span>
        </router-link>
      </nav>

      <!-- User + sync footer -->
      <div class="shrink-0 border-t border-white/[0.06]">
        <!-- Sync status -->
        <router-link
          to="/sync"
          class="flex items-center gap-2.5 group no-underline"
          :class="collapsed ? 'justify-center px-2 py-2.5' : 'px-4 py-2.5'"
          aria-label="Sync status"
        >
          <div
            class="w-[7px] h-[7px] shrink-0 rounded-full transition-colors"
            :class="{
              'bg-blue-400 pulse-dot': isSyncing,
              'bg-red-400': !isSyncing && syncStore.lastCompletedRun?.status === 'failed',
              'bg-emerald-400': !isSyncing && syncStore.lastCompletedRun?.status !== 'failed'
            }"
          />
          <span v-if="!collapsed" class="text-[11px] text-slate-500 group-hover:text-slate-300 transition-colors truncate leading-none">
            <template v-if="isSyncing">Sync in progress…</template>
            <template v-else-if="syncStore.lastCompletedRun">Last sync completed</template>
            <template v-else>Never synced</template>
          </span>
        </router-link>

        <!-- User info (authenticated) -->
        <div
          v-if="auth.user"
          class="border-t border-white/[0.06] flex items-center"
          :class="collapsed ? 'justify-center px-2 py-2.5' : 'gap-2.5 px-4 py-2.5'"
        >
          <!-- Avatar circle -->
          <div class="w-7 h-7 rounded-full bg-indigo-500/20 flex items-center justify-center shrink-0" :title="collapsed ? `${auth.user.username} (${auth.user.role})` : undefined">
            <span class="text-[11px] font-semibold text-indigo-400 uppercase">{{ auth.user.username.charAt(0) }}</span>
          </div>

          <template v-if="!collapsed">
            <div class="flex-1 min-w-0">
              <p class="text-[12px] font-medium text-slate-300 truncate leading-none">{{ auth.user.username }}</p>
              <span class="inline-block mt-1 text-[9px] font-medium uppercase tracking-wider px-1.5 py-0.5 rounded-full leading-none" :class="roleBadge">
                {{ auth.user.role }}
              </span>
            </div>
            <button
              @click="handleLogout"
              class="p-1 rounded hover:bg-white/[0.06] text-slate-500 hover:text-red-400 transition"
              aria-label="Sign out"
              title="Sign out"
            >
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
            </button>
          </template>
        </div>

      </div>
    </aside>

    <!-- ── Main area ── -->
    <div class="flex flex-col flex-1 min-w-0 overflow-hidden">

      <!-- Topbar -->
      <header class="flex items-center justify-between px-6 h-[52px] shrink-0" style="background: var(--surface); border-bottom: 1px solid var(--border);">
        <div class="flex items-center gap-3">
          <!-- Expand sidebar button in topbar when collapsed -->
          <button
            v-if="collapsed"
            @click="toggleSidebar"
            class="p-1 -ml-1 rounded transition" style="color: var(--text-3);"
            aria-label="Expand sidebar"
          >
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <h1 class="text-[15px] font-semibold tracking-[-0.2px]" style="color: var(--heading);">{{ pageTitle }}</h1>
        </div>
        <div class="flex items-center gap-3">
          <!-- Tenant switcher (SaaS mode, super_admin only) -->
          <div v-if="isSaas && auth.isSuperAdmin && tenants.length" class="relative">
            <button
              class="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg transition-colors" style="color: var(--text-2); background: var(--surface-hover);"
              aria-label="Switch tenant"
              @click="tenantDropdownOpen = !tenantDropdownOpen"
            >
              <svg class="w-3.5 h-3.5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
              {{ activeTenantName }}
              <svg class="w-3 h-3 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            <div v-if="tenantDropdownOpen" class="fixed inset-0 z-40" @click="tenantDropdownOpen = false" />
            <div
              v-if="tenantDropdownOpen"
              class="absolute right-0 mt-1 w-48 rounded-lg shadow-lg z-50 py-1" style="background: var(--surface); border: 1px solid var(--border);"
            >
              <button
                class="w-full text-left px-3 py-2 text-xs transition-colors"
                :class="!activeTenantSlug ? 'font-semibold' : ''" :style="{ color: !activeTenantSlug ? 'var(--primary)' : 'var(--text-2)' }"
                @click="switchTenant(null)"
              >
                Default (no tenant)
              </button>
              <button
                v-for="t in tenants"
                :key="t.slug"
                class="w-full text-left px-3 py-2 text-xs transition-colors"
                :class="activeTenantSlug === t.slug ? 'font-semibold' : ''"
                :style="{ color: activeTenantSlug === t.slug ? 'var(--primary)' : 'var(--text-2)' }"
                @mouseenter="($event.target as HTMLElement).style.background = 'var(--surface-hover)'"
                @mouseleave="($event.target as HTMLElement).style.background = ''"
                @click="switchTenant(t.slug)"
              >
                {{ t.name }}
              </button>
            </div>
          </div>
          <span v-if="auth.user" class="text-xs" style="color: var(--text-3);">{{ auth.user.username }}</span>
        </div>
      </header>

      <!-- Page content -->
      <main ref="mainRef" id="main-content" tabindex="-1" class="flex-1 overflow-y-auto outline-none" aria-label="Page content">
        <router-view />
      </main>

    </div>

    <!-- Global toast notification -->
    <Teleport to="body">
      <Transition name="toast">
        <div
          v-if="toast.visible.value"
          class="fixed top-4 right-4 z-[100] px-4 py-3 rounded-lg shadow-lg text-sm font-medium max-w-sm"
          :style="{
            background: toast.type.value === 'success' ? 'var(--success-bg, #16a34a)' : toast.type.value === 'error' ? 'var(--error-bg, #dc2626)' : 'var(--accent-bg, #2563eb)',
            color: toast.type.value === 'success' ? 'var(--success-text, #fff)' : toast.type.value === 'error' ? 'var(--error-text, #fff)' : 'var(--accent-text, #fff)',
            border: '1px solid ' + (toast.type.value === 'success' ? 'var(--success-border, #16a34a)' : toast.type.value === 'error' ? 'var(--error-border, #dc2626)' : 'var(--accent-border, #2563eb)'),
          }"
          role="status"
          aria-live="polite"
        >
          <div class="flex items-center justify-between gap-2">
            <span>{{ toast.message.value }}</span>
            <button class="opacity-70 hover:opacity-100" @click="toast.dismiss()">&times;</button>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>
