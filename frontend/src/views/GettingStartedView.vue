<!--
  Getting Started — interactive guide split into two perspectives:
  1. Tenant Guide: the core asset classification workflow (all users)
  2. Platform Guide: SaaS administration (super_admin only features)
-->
<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useAuthStore } from '@/stores/useAuthStore'
import { useDeployment } from '@/composables/useDeployment'

const auth = useAuthStore()
const { isSaas } = useDeployment()

const activeTab = ref<'tenant' | 'platform'>('tenant')

const tenantSections = [
  { id: 'overview',         label: 'Overview' },
  { id: 'step-settings',    label: '1 · Settings' },
  { id: 'step-sync',        label: '2 · Sync Data' },
  { id: 'step-groups',      label: '3 · Groups' },
  { id: 'step-taxonomy',    label: '4 · Taxonomy' },
  { id: 'step-tags',        label: '5 · Tag Rules' },
  { id: 'step-fingerprint', label: '6 · Fingerprints' },
  { id: 'step-proposals',   label: '7 · Proposals' },
  { id: 'step-library',     label: '8 · Library' },
  { id: 'step-classify',    label: '9 · Classification' },
  { id: 'step-anomalies',   label: '10 · Anomalies' },
  { id: 'step-compliance',  label: '11 · Compliance' },
  { id: 'reference',        label: 'Reference' },
]

const platformSections = [
  { id: 'p-overview',       label: 'Overview' },
  { id: 'p-tenants',        label: 'Tenant Management' },
  { id: 'p-users',          label: 'User Management' },
  { id: 'p-library-src',    label: 'Library Sources' },
  { id: 'p-compliance',     label: 'Compliance Reports' },
  { id: 'p-webhooks',       label: 'Webhooks' },
  { id: 'p-audit',          label: 'Audit Log' },
  { id: 'p-roles',          label: 'Role Reference' },
]

const sections = computed(() => activeTab.value === 'tenant' ? tenantSections : platformSections)
const activeSection = ref('overview')

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

watch(activeTab, () => {
  activeSection.value = sections.value[0].id
  window.scrollTo({ top: 0, behavior: 'smooth' })
})

let observer: IntersectionObserver | null = null

function setupObserver() {
  observer?.disconnect()
  observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          activeSection.value = entry.target.id
          break
        }
      }
    },
    { rootMargin: '-10% 0px -75% 0px', threshold: 0 },
  )
  sections.value.forEach(({ id }) => {
    const el = document.getElementById(id)
    if (el) observer!.observe(el)
  })
}

let _observerTimer: ReturnType<typeof setTimeout> | null = null
onMounted(setupObserver)
watch(activeTab, () => {
  if (_observerTimer) clearTimeout(_observerTimer)
  _observerTimer = setTimeout(setupObserver, 50)
})
onUnmounted(() => {
  if (_observerTimer) clearTimeout(_observerTimer)
  observer?.disconnect()
})
</script>

<template>
  <div class="flex min-h-full">

    <!-- ── Sticky TOC sidebar ─────────────────────────────────────────────── -->
    <nav role="navigation" aria-label="Table of contents" class="hidden lg:block w-52 shrink-0 sticky top-0 self-start pt-8 pb-6 pl-6 pr-2">
      <!-- Tab switcher -->
      <div class="flex gap-1 mb-4 p-0.5 rounded-lg" style="background: var(--surface-hover);">
        <button
          :class="activeTab === 'tenant' ? 'shadow-sm' : ''"
          :style="activeTab === 'tenant' ? 'background: var(--surface); color: var(--text-1);' : 'color: var(--text-3);'"
          class="flex-1 px-2 py-1.5 rounded-md text-[11px] font-medium transition-all"
          @click="activeTab = 'tenant'"
        >Tenant</button>
        <button
          v-if="isSaas && auth.isSuperAdmin"
          :class="activeTab === 'platform' ? 'shadow-sm' : ''"
          :style="activeTab === 'platform' ? 'background: var(--surface); color: var(--text-1);' : 'color: var(--text-3);'"
          class="flex-1 px-2 py-1.5 rounded-md text-[11px] font-medium transition-all"
          @click="activeTab = 'platform'"
        >Platform</button>
      </div>

      <p class="text-[10px] font-semibold uppercase tracking-widest mb-3" style="color: var(--text-3);">On this page</p>
      <ul class="space-y-0.5">
        <li v-for="s in sections" :key="s.id">
          <button
            :aria-label="'Scroll to ' + s.label"
            :aria-current="activeSection === s.id ? 'true' : undefined"
            class="w-full text-left px-2.5 py-1.5 rounded-md text-[12px] transition-colors"
            :class="activeSection === s.id
              ? 'font-semibold'
              : ''"
            :style="activeSection === s.id ? 'color: var(--brand-primary); background: var(--info-bg);' : 'color: var(--text-3);'"
            @click="scrollTo(s.id)"
          >{{ s.label }}</button>
        </li>
      </ul>
    </nav>

    <!-- ── Main content ───────────────────────────────────────────────────── -->
    <div class="flex-1 max-w-2xl px-8 py-8 space-y-14">

      <!-- Mobile tab switcher -->
      <div class="flex gap-2 lg:hidden mb-4">
        <button
          :style="activeTab === 'tenant' ? 'background: var(--brand-primary); color: white;' : 'background: var(--surface-hover); color: var(--text-2);'"
          class="px-4 py-2 rounded-lg text-sm font-medium"
          @click="activeTab = 'tenant'"
        >Tenant Guide</button>
        <button
          v-if="isSaas && auth.isSuperAdmin"
          :style="activeTab === 'platform' ? 'background: var(--brand-primary); color: white;' : 'background: var(--surface-hover); color: var(--text-2);'"
          class="px-4 py-2 rounded-lg text-sm font-medium"
          @click="activeTab = 'platform'"
        >Platform Guide</button>
      </div>

      <!-- ================================================================= -->
      <!-- TENANT GUIDE                                                       -->
      <!-- ================================================================= -->
      <template v-if="activeTab === 'tenant'">

        <!-- ── Overview ──────────────────────────────────────────────────── -->
        <section id="overview" class="scroll-mt-4">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-8 h-8 rounded-xl flex items-center justify-center shrink-0" style="background: var(--info-bg);">
              <svg aria-hidden="true" class="w-4 h-4" style="color: var(--info-text);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h1 class="text-[22px] font-bold" style="color: var(--heading);">Getting Started</h1>
          </div>
          <p class="text-[14px] leading-relaxed mb-5" style="color: var(--text-2);">
            Sentora classifies SentinelOne agents into the correct groups based on the software
            installed on each endpoint. It pulls live data from the SentinelOne API, lets you define
            per-group <strong>fingerprints</strong> (glob patterns that identify group membership),
            then runs a scoring pass and flags agents that appear to be in the wrong group.
          </p>

          <!-- Process flow -->
          <div class="rounded-xl p-5" style="background: var(--surface-alt); border: 1px solid var(--border);">
            <p class="text-[10px] font-semibold uppercase tracking-widest mb-4" style="color: var(--text-3);">Full workflow at a glance</p>
            <div class="flex flex-wrap items-center gap-y-3 gap-x-2 text-[12px]">
              <div v-for="(step, i) in [
                { label: 'Settings',     bg: 'var(--badge-bg)',        fg: 'var(--badge-text)' },
                { label: 'Sync',         bg: 'var(--info-bg)',         fg: 'var(--info-text)' },
                { label: 'Groups',       bg: 'var(--badge-bg)',        fg: 'var(--badge-text)' },
                { label: 'Taxonomy',     bg: 'var(--status-ok-bg)',    fg: 'var(--status-ok-text)' },
                { label: 'Tags',         bg: 'var(--status-error-bg)', fg: 'var(--status-error-text)' },
                { label: 'Fingerprints', bg: 'var(--accent-bg)',       fg: 'var(--accent-text)' },
                { label: 'Proposals',    bg: 'var(--accent-bg)',       fg: 'var(--accent-text)' },
                { label: 'Library',      bg: 'var(--scope-site-bg)',   fg: 'var(--scope-site-text)' },
                { label: 'Classify',     bg: 'var(--info-bg)',         fg: 'var(--info-text)' },
                { label: 'Anomalies',    bg: 'var(--status-warn-bg)',  fg: 'var(--status-warn-text)' },
                { label: 'Compliance',   bg: 'var(--scope-site-bg)',   fg: 'var(--scope-site-text)' },
              ]" :key="step.label" class="flex items-center gap-2">
                <div class="flex flex-col items-center gap-1">
                  <div class="w-9 h-9 rounded-lg flex items-center justify-center" :style="{ background: step.bg }">
                    <span class="text-[11px] font-bold" :style="{ color: step.fg }">{{ i + 1 }}</span>
                  </div>
                  <span class="font-medium" style="color: var(--text-2);">{{ step.label }}</span>
                </div>
                <span v-if="i < 10" class="font-bold text-[16px] mb-4" style="color: var(--text-3);">&rarr;</span>
              </div>
            </div>
          </div>
        </section>

        <!-- ── Step 1: Settings ──────────────────────────────────────────── -->
        <section id="step-settings" class="scroll-mt-4">
          <div class="flex items-center gap-3 mb-4">
            <span class="w-7 h-7 rounded-full text-[13px] font-bold flex items-center justify-center shrink-0" style="background: var(--badge-bg); color: var(--badge-text);">1</span>
            <h2 class="text-[18px] font-bold" style="color: var(--heading);">Configure Settings</h2>
          </div>
          <p class="text-[14px] leading-relaxed mb-4" style="color: var(--text-2);">
            Before anything works, Sentora needs a SentinelOne API token and your account scope.
            Open <strong>Settings</strong> and fill in:
          </p>
          <ul class="space-y-2 mb-5 ml-1">
            <li class="flex gap-3 text-[14px]">
              <span class="shrink-0 mt-1 w-1.5 h-1.5 rounded-full" style="background: var(--text-3);"></span>
              <div><span class="font-medium" style="color: var(--text-2);">API URL</span> <span style="color: var(--text-3);">&mdash; your SentinelOne management console base URL.</span></div>
            </li>
            <li class="flex gap-3 text-[14px]">
              <span class="shrink-0 mt-1 w-1.5 h-1.5 rounded-full" style="background: var(--text-3);"></span>
              <div><span class="font-medium" style="color: var(--text-2);">API Token</span> <span style="color: var(--text-3);">&mdash; a service-user token with visibility on the accounts/sites you want to analyse.</span></div>
            </li>
            <li class="flex gap-3 text-[14px]">
              <span class="shrink-0 mt-1 w-1.5 h-1.5 rounded-full" style="background: var(--text-3);"></span>
              <div><span class="font-medium" style="color: var(--text-2);">Account IDs / Site IDs</span> <span style="color: var(--text-3);">&mdash; scope which parts of your fleet are synced.</span></div>
            </li>
            <li class="flex gap-3 text-[14px]">
              <span class="shrink-0 mt-1 w-1.5 h-1.5 rounded-full" style="background: var(--text-3);"></span>
              <div><span class="font-medium" style="color: var(--text-2);">Scoring thresholds</span> <span style="color: var(--text-3);">&mdash; confidence and ambiguity thresholds used by classification (sane defaults pre-filled).</span></div>
            </li>
            <li class="flex gap-3 text-[14px]">
              <span class="shrink-0 mt-1 w-1.5 h-1.5 rounded-full" style="background: var(--text-3);"></span>
              <div><span class="font-medium" style="color: var(--text-2);">Scheduled refresh</span> <span style="color: var(--text-3);">&mdash; optional interval (1&ndash;1440 min) to automatically re-sync and re-classify.</span></div>
            </li>
          </ul>
          <router-link to="/settings" aria-label="Open Settings page" class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium transition-colors no-underline" style="background: var(--brand-primary); color: white;">Open Settings &rarr;</router-link>
        </section>

        <!-- ── Step 2: Sync ──────────────────────────────────────────────── -->
        <section id="step-sync" class="scroll-mt-4">
          <div class="flex items-center gap-3 mb-4">
            <span class="w-7 h-7 rounded-full text-[13px] font-bold flex items-center justify-center shrink-0" style="background: var(--info-bg); color: var(--info-text);">2</span>
            <h2 class="text-[18px] font-bold" style="color: var(--heading);">Sync Data from SentinelOne</h2>
          </div>
          <p class="text-[14px] leading-relaxed mb-4" style="color: var(--text-2);">
            Everything starts with a sync. Sentora pulls four datasets in sequence:
            <strong>Sites</strong>, <strong>Groups</strong>, <strong>Agents</strong>, and <strong>Installed Apps</strong>.
            Incremental sync resumes from the last cursor watermark.
          </p>
          <div class="rounded-xl px-4 py-3 text-[13px] mb-5 flex gap-2" style="background: var(--info-bg); border: 1px solid var(--info-text); color: var(--info-text);">
            <span class="shrink-0 font-bold">Tip</span>
            <span>Sync before doing anything else. Watch the live four-phase progress bar &mdash; it streams updates over WebSocket.</span>
          </div>
          <router-link to="/sync" aria-label="Open Sync page" class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium transition-colors no-underline" style="background: var(--brand-primary); color: white;">Open Sync &rarr;</router-link>
        </section>

        <!-- ── Step 3: Groups ────────────────────────────────────────────── -->
        <section id="step-groups" class="scroll-mt-4">
          <div class="flex items-center gap-3 mb-4">
            <span class="w-7 h-7 rounded-full text-[13px] font-bold flex items-center justify-center shrink-0" style="background: var(--badge-bg); color: var(--badge-text);">3</span>
            <h2 class="text-[18px] font-bold" style="color: var(--heading);">Browse Groups</h2>
          </div>
          <p class="text-[14px] leading-relaxed mb-4" style="color: var(--text-2);">
            The Groups page shows every SentinelOne group pulled during sync as a card grid.
            Each card displays agent count, OS breakdown, and fingerprint status.
            Click any card to jump directly into its Fingerprint Editor.
          </p>
          <router-link to="/groups" aria-label="Open Groups page" class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium transition-colors no-underline" style="background: var(--brand-primary); color: white;">Open Groups &rarr;</router-link>
        </section>

        <!-- ── Step 4: Taxonomy ──────────────────────────────────────────── -->
        <section id="step-taxonomy" class="scroll-mt-4">
          <div class="flex items-center gap-3 mb-4">
            <span class="w-7 h-7 rounded-full text-[13px] font-bold flex items-center justify-center shrink-0" style="background: var(--status-ok-bg); color: var(--status-ok-text);">4</span>
            <h2 class="text-[18px] font-bold" style="color: var(--heading);">Review the Software Taxonomy</h2>
          </div>
          <p class="text-[14px] leading-relaxed mb-4" style="color: var(--text-2);">
            The taxonomy is a curated catalog of known software entries, each with glob patterns and a category.
            It serves as the vocabulary for building fingerprints. A pre-seeded set loads on first start.
          </p>
          <table class="w-full text-[13px] rounded-xl overflow-hidden mb-5" style="border: 1px solid var(--border);">
            <thead style="background: var(--surface-inset);">
              <tr>
                <th class="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-widest w-[25%]" style="color: var(--text-3);">Concept</th>
                <th class="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">What it means</th>
              </tr>
            </thead>
            <tbody class="divide-y" style="border-color: var(--border-light);">
              <tr><td class="px-3 py-2.5 font-medium" style="color: var(--text-2);">Entry</td><td class="px-3 py-2.5" style="color: var(--text-3);">A named piece of software (e.g. "VMware Tools")</td></tr>
              <tr><td class="px-3 py-2.5 font-medium" style="color: var(--text-2);">Pattern</td><td class="px-3 py-2.5" style="color: var(--text-3);">Glob matched against <code class="px-1 rounded text-[11px] font-mono" style="background: var(--surface-inset);">normalized_name</code> &mdash; supports <code class="px-1 rounded text-[11px] font-mono" style="background: var(--surface-inset);">*</code> and <code class="px-1 rounded text-[11px] font-mono" style="background: var(--surface-inset);">?</code></td></tr>
              <tr><td class="px-3 py-2.5 font-medium" style="color: var(--text-2);">Category</td><td class="px-3 py-2.5" style="color: var(--text-3);">Logical grouping: virtualisation, security, devtools, etc.</td></tr>
              <tr><td class="px-3 py-2.5 font-medium" style="color: var(--text-2);">Universal</td><td class="px-3 py-2.5" style="color: var(--text-3);">Excluded from fingerprint scoring &mdash; use for OS noise or AV agents present everywhere</td></tr>
            </tbody>
          </table>
          <router-link to="/taxonomy" aria-label="Open Taxonomy page" class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium transition-colors no-underline" style="background: var(--brand-primary); color: white;">Open Taxonomy &rarr;</router-link>
        </section>

        <!-- ── Step 5: Tag Rules ─────────────────────────────────────────── -->
        <section id="step-tags" class="scroll-mt-4">
          <div class="flex items-center gap-3 mb-4">
            <span class="w-7 h-7 rounded-full text-[13px] font-bold flex items-center justify-center shrink-0" style="background: var(--status-error-bg); color: var(--status-error-text);">5</span>
            <h2 class="text-[18px] font-bold" style="color: var(--heading);">Configure Tag Rules</h2>
          </div>
          <p class="text-[14px] leading-relaxed mb-4" style="color: var(--text-2);">
            Tag rules let you automatically apply SentinelOne tags to agents based on their installed software,
            OS, or group membership. Rules are evaluated during sync and classification &mdash; matching agents
            receive the specified tag in SentinelOne.
          </p>
          <ul class="space-y-2 mb-5 ml-1">
            <li class="flex gap-3 text-[14px]">
              <span class="shrink-0 mt-1 w-1.5 h-1.5 rounded-full" style="background: var(--status-error-text);"></span>
              <div><span class="font-medium" style="color: var(--text-2);">Conditions</span> <span style="color: var(--text-3);">&mdash; glob patterns or field matchers that define when a tag applies.</span></div>
            </li>
            <li class="flex gap-3 text-[14px]">
              <span class="shrink-0 mt-1 w-1.5 h-1.5 rounded-full" style="background: var(--status-error-text);"></span>
              <div><span class="font-medium" style="color: var(--text-2);">AND / OR logic</span> <span style="color: var(--text-3);">&mdash; combine multiple conditions per rule.</span></div>
            </li>
            <li class="flex gap-3 text-[14px]">
              <span class="shrink-0 mt-1 w-1.5 h-1.5 rounded-full" style="background: var(--status-error-text);"></span>
              <div><span class="font-medium" style="color: var(--text-2);">Preview</span> <span style="color: var(--text-3);">&mdash; test your rule against current data before activating.</span></div>
            </li>
          </ul>
          <router-link to="/tags" aria-label="Open Tag Rules page" class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium transition-colors no-underline" style="background: var(--brand-primary); color: white;">Open Tag Rules &rarr;</router-link>
        </section>

        <!-- ── Step 6: Fingerprints ──────────────────────────────────────── -->
        <section id="step-fingerprint" class="scroll-mt-4">
          <div class="flex items-center gap-3 mb-4">
            <span class="w-7 h-7 rounded-full text-[13px] font-bold flex items-center justify-center shrink-0" style="background: var(--accent-bg); color: var(--accent-text);">6</span>
            <h2 class="text-[18px] font-bold" style="color: var(--heading);">Build Fingerprints</h2>
          </div>
          <p class="text-[14px] leading-relaxed mb-4" style="color: var(--text-2);">
            A <strong>fingerprint</strong> is an ordered list of weighted glob markers that describe what software
            a correctly-placed agent in that group should have. The three-panel editor lets you browse the
            taxonomy catalog, drag markers into the definition, and preview which agents match.
          </p>
          <p class="text-[14px] font-semibold mb-2" style="color: var(--text-1);">Using Suggestions (Analyze)</p>
          <p class="text-[14px] leading-relaxed mb-5" style="color: var(--text-2);">
            Click <strong>Analyze</strong> to run a TF-IDF computation that ranks apps by how strongly they
            distinguish <em>this group</em> from all others. Accept suggestions to add them as markers.
          </p>
          <router-link to="/fingerprints" aria-label="Open Fingerprint Editor page" class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium transition-colors no-underline" style="background: var(--brand-primary); color: white;">Open Fingerprint Editor &rarr;</router-link>
        </section>

        <!-- ── Step 7: Proposals ─────────────────────────────────────────── -->
        <section id="step-proposals" class="scroll-mt-4">
          <div class="flex items-center gap-3 mb-4">
            <span class="w-7 h-7 rounded-full text-[13px] font-bold flex items-center justify-center shrink-0" style="background: var(--accent-bg); color: var(--accent-text);">7</span>
            <h2 class="text-[18px] font-bold" style="color: var(--heading);">Review Auto-Proposals</h2>
          </div>
          <p class="text-[14px] leading-relaxed mb-4" style="color: var(--text-2);">
            Instead of manually building every fingerprint, the <strong>Proposals</strong> page computes
            discriminative markers for all groups at once using a lift-based algorithm. Review lift scores,
            spot cross-group conflicts, and apply or dismiss proposals individually or in bulk.
          </p>
          <router-link to="/fingerprints/proposals" aria-label="Open Proposals page" class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium transition-colors no-underline" style="background: var(--brand-primary); color: white;">Open Proposals &rarr;</router-link>
        </section>

        <!-- ── Step 8: Library ───────────────────────────────────────────── -->
        <section id="step-library" class="scroll-mt-4">
          <div class="flex items-center gap-3 mb-4">
            <span class="w-7 h-7 rounded-full text-[13px] font-bold flex items-center justify-center shrink-0" style="background: var(--scope-site-bg); color: var(--scope-site-text);">8</span>
            <h2 class="text-[18px] font-bold" style="color: var(--heading);">Fingerprint Library</h2>
          </div>
          <p class="text-[14px] leading-relaxed mb-4" style="color: var(--text-2);">
            The library provides pre-built fingerprint templates curated by the platform administrator.
            Instead of building markers from scratch, you can subscribe your groups to library entries.
          </p>
          <ul class="space-y-2 mb-5 ml-1">
            <li class="flex gap-3 text-[14px]">
              <span class="shrink-0 mt-1 w-1.5 h-1.5 rounded-full" style="background: var(--scope-site-text);"></span>
              <div><span class="font-medium" style="color: var(--text-2);">Browse</span> <span style="color: var(--text-3);">&mdash; search and filter published entries by category, source, or keyword.</span></div>
            </li>
            <li class="flex gap-3 text-[14px]">
              <span class="shrink-0 mt-1 w-1.5 h-1.5 rounded-full" style="background: var(--scope-site-text);"></span>
              <div><span class="font-medium" style="color: var(--text-2);">Subscribe</span> <span style="color: var(--text-3);">&mdash; link a group to a library entry. Markers are copied into the group's fingerprint.</span></div>
            </li>
            <li class="flex gap-3 text-[14px]">
              <span class="shrink-0 mt-1 w-1.5 h-1.5 rounded-full" style="background: var(--scope-site-text);"></span>
              <div><span class="font-medium" style="color: var(--text-2);">Auto-update</span> <span style="color: var(--text-3);">&mdash; when enabled, subscribed groups automatically receive new markers when the library entry is updated.</span></div>
            </li>
          </ul>
          <div class="rounded-xl px-4 py-3 text-[13px] mb-5 flex gap-2" style="background: var(--scope-site-bg); border: 1px solid var(--scope-site-text); color: var(--scope-site-text);">
            <span class="shrink-0 font-bold">Note</span>
            <span>Library entries are shared across all tenants. You can mix library-sourced markers with your own manual and statistical markers in the same fingerprint.</span>
          </div>
          <router-link to="/library" aria-label="Open Library page" class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium transition-colors no-underline" style="background: var(--brand-primary); color: white;">Open Library &rarr;</router-link>
        </section>

        <!-- ── Step 9: Classification ────────────────────────────────────── -->
        <section id="step-classify" class="scroll-mt-4">
          <div class="flex items-center gap-3 mb-4">
            <span class="w-7 h-7 rounded-full text-[13px] font-bold flex items-center justify-center shrink-0" style="background: var(--info-bg); color: var(--info-text);">9</span>
            <h2 class="text-[18px] font-bold" style="color: var(--heading);">Run Classification</h2>
          </div>
          <p class="text-[14px] leading-relaxed mb-4" style="color: var(--text-2);">
            Trigger a classification run to score every agent against every fingerprint.
            Each agent's installed apps are matched against marker patterns; the fingerprint with the
            highest total score becomes the <strong>suggested group</strong>.
          </p>
          <table class="w-full text-[13px] rounded-xl overflow-hidden mb-5" style="border: 1px solid var(--border);">
            <thead style="background: var(--surface-inset);">
              <tr>
                <th class="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-widest w-[28%]" style="color: var(--text-3);">Verdict</th>
                <th class="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Meaning</th>
              </tr>
            </thead>
            <tbody class="divide-y" style="border-color: var(--border-light);">
              <tr><td class="px-3 py-2.5"><span class="inline-flex px-2 py-0.5 rounded text-[11px] font-semibold" style="background: var(--status-ok-bg); color: var(--status-ok-text);">correct</span></td><td class="px-3 py-2.5" style="color: var(--text-3);">Current group matches top-scoring fingerprint</td></tr>
              <tr><td class="px-3 py-2.5"><span class="inline-flex px-2 py-0.5 rounded text-[11px] font-semibold" style="background: var(--status-warn-bg); color: var(--status-warn-text);">misclassified</span></td><td class="px-3 py-2.5" style="color: var(--text-3);">A different fingerprint scored higher</td></tr>
              <tr><td class="px-3 py-2.5"><span class="inline-flex px-2 py-0.5 rounded text-[11px] font-semibold" style="background: var(--status-warn-bg); color: var(--status-warn-text);">ambiguous</span></td><td class="px-3 py-2.5" style="color: var(--text-3);">Two+ groups scored within the tie threshold</td></tr>
              <tr><td class="px-3 py-2.5"><span class="inline-flex px-2 py-0.5 rounded text-[11px] font-semibold" style="background: var(--badge-bg); color: var(--badge-text);">unclassifiable</span></td><td class="px-3 py-2.5" style="color: var(--text-3);">No fingerprint reached minimum confidence</td></tr>
            </tbody>
          </table>
          <router-link to="/classification" aria-label="Open Classification page" class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium transition-colors no-underline" style="background: var(--brand-primary); color: white;">Open Classification &rarr;</router-link>
        </section>

        <!-- ── Step 10: Anomalies ────────────────────────────────────────── -->
        <section id="step-anomalies" class="scroll-mt-4">
          <div class="flex items-center gap-3 mb-4">
            <span class="w-7 h-7 rounded-full text-[13px] font-bold flex items-center justify-center shrink-0" style="background: var(--status-warn-bg); color: var(--status-warn-text);">10</span>
            <h2 class="text-[18px] font-bold" style="color: var(--heading);">Review Anomalies</h2>
          </div>
          <p class="text-[14px] leading-relaxed mb-4" style="color: var(--text-2);">
            The Anomalies page surfaces agents flagged during classification. Each entry shows the verdict,
            numeric match scores, and anomaly reasons. Click any row to open the <strong>Agent Detail</strong>
            deep-dive with full match-score breakdown, marker pills, and installed-apps table.
          </p>
          <p class="text-[14px] leading-relaxed mb-5" style="color: var(--text-2);">
            Click <strong>Acknowledge</strong> to mark an agent as reviewed. Acknowledged agents are dimmed
            across views but remain in the dataset for audit purposes.
          </p>
          <router-link to="/anomalies" aria-label="Open Anomalies page" class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium transition-colors no-underline" style="background: var(--brand-primary); color: white;">Open Anomalies &rarr;</router-link>
        </section>

        <!-- ── Step 11: Compliance ───────────────────────────────────────── -->
        <section id="step-compliance" class="scroll-mt-4">
          <div class="flex items-center gap-3 mb-4">
            <span class="w-7 h-7 rounded-full text-[13px] font-bold flex items-center justify-center shrink-0" style="background: var(--scope-site-bg); color: var(--scope-site-text);">11</span>
            <h2 class="text-[18px] font-bold" style="color: var(--heading);">Compliance Dashboard</h2>
          </div>
          <p class="text-[14px] leading-relaxed mb-4" style="color: var(--text-2);">
            The compliance dashboard evaluates your environment against <strong>SOC 2 Type II</strong> and
            <strong>ISO 27001</strong> controls in real time. Evidence is collected automatically from your
            existing data &mdash; users, audit logs, backups, classifications, and webhooks.
          </p>
          <ul class="space-y-2 mb-5 ml-1">
            <li class="flex gap-3 text-[14px]">
              <span class="shrink-0 mt-1 w-1.5 h-1.5 rounded-full" style="background: var(--scope-site-text);"></span>
              <div><span class="font-medium" style="color: var(--text-2);">Real-time scoring</span> <span style="color: var(--text-3);">&mdash; each control shows passing, warning, or failing status with evidence counts.</span></div>
            </li>
            <li class="flex gap-3 text-[14px]">
              <span class="shrink-0 mt-1 w-1.5 h-1.5 rounded-full" style="background: var(--scope-site-text);"></span>
              <div><span class="font-medium" style="color: var(--text-2);">Report generation</span> <span style="color: var(--text-3);">&mdash; one-click PDF/CSV reports for auditor delivery.</span></div>
            </li>
            <li class="flex gap-3 text-[14px]">
              <span class="shrink-0 mt-1 w-1.5 h-1.5 rounded-full" style="background: var(--scope-site-text);"></span>
              <div><span class="font-medium" style="color: var(--text-2);">Framework tabs</span> <span style="color: var(--text-3);">&mdash; switch between SOC 2 and ISO 27001 views.</span></div>
            </li>
          </ul>
          <router-link to="/compliance" aria-label="Open Compliance page" class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium transition-colors no-underline" style="background: var(--brand-primary); color: white;">Open Compliance &rarr;</router-link>
        </section>

        <!-- ── Reference ─────────────────────────────────────────────────── -->
        <section id="reference" class="scroll-mt-4 pb-16">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-8 h-8 rounded-xl flex items-center justify-center shrink-0" style="background: var(--badge-bg);">
              <svg aria-hidden="true" class="w-4 h-4" style="color: var(--badge-text);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            </div>
            <h2 class="text-[18px] font-bold" style="color: var(--heading);">Quick Reference</h2>
          </div>

          <table class="w-full text-[13px] rounded-xl overflow-hidden mb-6" style="border: 1px solid var(--border);">
            <thead style="background: var(--surface-inset);">
              <tr>
                <th class="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Page</th>
                <th class="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Purpose</th>
                <th class="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Key actions</th>
              </tr>
            </thead>
            <tbody class="divide-y" style="border-color: var(--border-light);">
              <tr v-for="row in [
                { page: 'Dashboard',          purpose: 'Health overview',               actions: 'Counts, last sync time, anomaly summary' },
                { page: 'Sync',               purpose: 'Pull SentinelOne data',         actions: 'Trigger full/incremental sync, watch 4-phase progress' },
                { page: 'Groups',             purpose: 'Browse agent groups',           actions: 'View counts, OS breakdown, open fingerprint editor' },
                { page: 'Taxonomy',           purpose: 'Software catalog',              actions: 'Add/edit entries, test glob patterns, manage categories' },
                { page: 'Tag Rules',          purpose: 'Auto-tag agents',               actions: 'Create rules with conditions, preview matches, activate' },
                { page: 'Fingerprint Editor', purpose: 'Define group identity',         actions: 'Drag markers, set weights, run Analyze' },
                { page: 'Proposals',          purpose: 'Auto-generated blueprints',     actions: 'Generate proposals, review lift scores, apply or dismiss' },
                { page: 'Library',            purpose: 'Shared fingerprint templates',  actions: 'Browse entries, subscribe groups, sync updates' },
                { page: 'Classification',     purpose: 'Score all agents',              actions: 'Trigger run, filter by verdict, export CSV / JSON' },
                { page: 'Anomalies',          purpose: 'Review flagged agents',         actions: 'Inspect reasons, acknowledge reviewed agents' },
                { page: 'Agent Detail',       purpose: 'Per-agent deep-dive',           actions: 'Match scores, marker pills, installed apps' },
                { page: 'App Detail',         purpose: 'Fleet-wide app analysis',       actions: 'Version distribution, group/site spread' },
                { page: 'Compliance',         purpose: 'SOC 2 / ISO 27001 controls',   actions: 'View real-time scores, generate reports, export CSV' },
                { page: 'Audit Log',          purpose: 'Change history',                actions: 'Browse all mutations with actor + timestamp' },
                { page: 'Settings',           purpose: 'Configuration',                 actions: 'API key, scope, thresholds, refresh interval' },
              ]" :key="row.page">
                <td class="px-3 py-2.5 font-medium" style="color: var(--text-2);">{{ row.page }}</td>
                <td class="px-3 py-2.5" style="color: var(--text-3);">{{ row.purpose }}</td>
                <td class="px-3 py-2.5" style="color: var(--text-3);">{{ row.actions }}</td>
              </tr>
            </tbody>
          </table>

          <div class="rounded-xl px-4 py-3 text-[13px]" style="background: var(--surface-alt); border: 1px solid var(--border); color: var(--text-2);">
            <p class="font-semibold mb-1.5" style="color: var(--text-1);">Glob pattern syntax</p>
            <p class="leading-relaxed">
              <code class="px-1.5 py-0.5 rounded text-[12px] font-mono" style="background: var(--surface); border: 1px solid var(--border);">*</code> matches any sequence of characters &nbsp;&middot;&nbsp;
              <code class="px-1.5 py-0.5 rounded text-[12px] font-mono" style="background: var(--surface); border: 1px solid var(--border);">?</code> matches a single character.
              Matching is always case-insensitive against <code class="px-1.5 py-0.5 rounded text-[12px] font-mono" style="background: var(--surface); border: 1px solid var(--border);">normalized_name</code>.
            </p>
          </div>
        </section>

      </template>

      <!-- ================================================================= -->
      <!-- PLATFORM GUIDE (super_admin)                                       -->
      <!-- ================================================================= -->
      <template v-if="activeTab === 'platform'">

        <!-- ── Platform Overview ─────────────────────────────────────────── -->
        <section id="p-overview" class="scroll-mt-4">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-8 h-8 rounded-xl flex items-center justify-center shrink-0" style="background: var(--accent-bg);">
              <svg aria-hidden="true" class="w-4 h-4" style="color: var(--accent-text);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
            </div>
            <h1 class="text-[22px] font-bold" style="color: var(--heading);">Platform Administration</h1>
          </div>
          <p class="text-[14px] leading-relaxed mb-5" style="color: var(--text-2);">
            As a <strong>super_admin</strong>, you manage the SaaS platform itself &mdash; tenants, shared
            library content, user accounts, and cross-tenant infrastructure. Tenant admins handle
            day-to-day operations within their own environment; you handle what spans across them.
          </p>

          <div class="rounded-xl p-5 mb-5" style="background: var(--accent-bg); border: 1px solid var(--accent-text);">
            <p class="text-[10px] font-semibold uppercase tracking-widest mb-3" style="color: var(--accent-text);">Role hierarchy</p>
            <div class="space-y-2 text-[13px]">
              <div class="flex items-center gap-3">
                <span class="inline-flex px-2 py-0.5 rounded text-[11px] font-semibold" style="background: var(--accent-bg); color: var(--accent-text);">super_admin</span>
                <span style="color: var(--text-2);">Platform operator &mdash; manages tenants, library sources, all cross-tenant features</span>
              </div>
              <div class="flex items-center gap-3">
                <span class="inline-flex px-2 py-0.5 rounded text-[11px] font-semibold" style="background: var(--info-bg); color: var(--info-text);">admin</span>
                <span style="color: var(--text-2);">Tenant administrator &mdash; manages users, settings, webhooks, compliance within their tenant</span>
              </div>
              <div class="flex items-center gap-3">
                <span class="inline-flex px-2 py-0.5 rounded text-[11px] font-semibold" style="background: var(--status-ok-bg); color: var(--status-ok-text);">analyst</span>
                <span style="color: var(--text-2);">Creates fingerprints, runs classification, manages subscriptions</span>
              </div>
              <div class="flex items-center gap-3">
                <span class="inline-flex px-2 py-0.5 rounded text-[11px] font-semibold" style="background: var(--badge-bg); color: var(--badge-text);">viewer</span>
                <span style="color: var(--text-2);">Read-only access to all data and dashboards</span>
              </div>
            </div>
          </div>
        </section>

        <!-- ── Tenant Management ─────────────────────────────────────────── -->
        <section id="p-tenants" class="scroll-mt-4">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-8 h-8 rounded-xl flex items-center justify-center shrink-0" style="background: var(--accent-bg);">
              <svg aria-hidden="true" class="w-4 h-4" style="color: var(--accent-text);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
            </div>
            <h2 class="text-[18px] font-bold" style="color: var(--heading);">Tenant Management</h2>
          </div>
          <p class="text-[14px] leading-relaxed mb-4" style="color: var(--text-2);">
            Each tenant gets an isolated MongoDB database. When multi-tenancy is enabled, use the
            tenant switcher in the top bar to switch context between tenants.
          </p>
          <ul class="space-y-2 mb-5 ml-1">
            <li class="flex gap-3 text-[14px]">
              <span class="shrink-0 mt-1 w-1.5 h-1.5 rounded-full" style="background: var(--accent-text);"></span>
              <div><span class="font-medium" style="color: var(--text-2);">Create</span> <span style="color: var(--text-3);">&mdash; provide a name and URL-safe slug. The database <code class="px-1 rounded text-[11px] font-mono" style="background: var(--surface-inset);">sentora_tenant_{slug}</code> is created automatically with all indexes.</span></div>
            </li>
            <li class="flex gap-3 text-[14px]">
              <span class="shrink-0 mt-1 w-1.5 h-1.5 rounded-full" style="background: var(--accent-text);"></span>
              <div><span class="font-medium" style="color: var(--text-2);">Disable</span> <span style="color: var(--text-3);">&mdash; suspends a tenant without deleting data.</span></div>
            </li>
            <li class="flex gap-3 text-[14px]">
              <span class="shrink-0 mt-1 w-1.5 h-1.5 rounded-full" style="background: var(--accent-text);"></span>
              <div><span class="font-medium" style="color: var(--text-2);">Delete</span> <span style="color: var(--text-3);">&mdash; removes the registry entry. The tenant database is <strong>not</strong> dropped automatically for safety.</span></div>
            </li>
          </ul>
          <div class="rounded-xl px-4 py-3 text-[13px] mb-5 flex gap-2" style="background: var(--warn-bg); border: 1px solid var(--warn-border); color: var(--warn-text);">
            <span class="shrink-0 font-bold">Note</span>
            <span>Enable multi-tenancy by setting <code class="px-1 rounded font-mono" style="background: var(--surface);">MULTI_TENANCY_ENABLED=true</code> in your environment. When disabled, all data lives in the default database.</span>
          </div>
          <router-link to="/tenants" aria-label="Open Tenants page" class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium transition-colors no-underline" style="background: var(--brand-primary); color: white;">Open Tenants &rarr;</router-link>
        </section>

        <!-- ── User Management ───────────────────────────────────────────── -->
        <section id="p-users" class="scroll-mt-4">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-8 h-8 rounded-xl flex items-center justify-center shrink-0" style="background: var(--info-bg);">
              <svg aria-hidden="true" class="w-4 h-4" style="color: var(--info-text);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            </div>
            <h2 class="text-[18px] font-bold" style="color: var(--heading);">User Management</h2>
          </div>
          <p class="text-[14px] leading-relaxed mb-4" style="color: var(--text-2);">
            Manage user accounts, roles, and access controls. The first registered user is automatically
            promoted to <strong>super_admin</strong>.
          </p>
          <ul class="space-y-2 mb-5 ml-1">
            <li class="flex gap-3 text-[14px]">
              <span class="shrink-0 mt-1 w-1.5 h-1.5 rounded-full" style="background: var(--info-text);"></span>
              <div><span class="font-medium" style="color: var(--text-2);">Role assignment</span> <span style="color: var(--text-3);">&mdash; promote or demote users between viewer, analyst, admin, and super_admin.</span></div>
            </li>
            <li class="flex gap-3 text-[14px]">
              <span class="shrink-0 mt-1 w-1.5 h-1.5 rounded-full" style="background: var(--info-text);"></span>
              <div><span class="font-medium" style="color: var(--text-2);">Disable accounts</span> <span style="color: var(--text-3);">&mdash; immediately blocks login without deleting the user record.</span></div>
            </li>
            <li class="flex gap-3 text-[14px]">
              <span class="shrink-0 mt-1 w-1.5 h-1.5 rounded-full" style="background: var(--info-text);"></span>
              <div><span class="font-medium" style="color: var(--text-2);">TOTP 2FA</span> <span style="color: var(--text-3);">&mdash; all users set up TOTP during registration. SSO users (OIDC/SAML) bypass local auth.</span></div>
            </li>
          </ul>
          <router-link to="/users" aria-label="Open Users page" class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium transition-colors no-underline" style="background: var(--brand-primary); color: white;">Open Users &rarr;</router-link>
        </section>

        <!-- ── Library Sources ───────────────────────────────────────────── -->
        <section id="p-library-src" class="scroll-mt-4">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-8 h-8 rounded-xl flex items-center justify-center shrink-0" style="background: var(--scope-site-bg);">
              <svg aria-hidden="true" class="w-4 h-4" style="color: var(--scope-site-text);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
              </svg>
            </div>
            <h2 class="text-[18px] font-bold" style="color: var(--heading);">Library Sources</h2>
          </div>
          <p class="text-[14px] leading-relaxed mb-4" style="color: var(--text-2);">
            Populate the shared fingerprint library by ingesting from external sources. Each source
            adapter fetches software definitions and creates published library entries that all tenants
            can browse and subscribe to.
          </p>
          <table class="w-full text-[13px] rounded-xl overflow-hidden mb-5" style="border: 1px solid var(--border);">
            <thead style="background: var(--surface-inset);">
              <tr>
                <th class="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Source</th>
                <th class="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Description</th>
              </tr>
            </thead>
            <tbody class="divide-y" style="border-color: var(--border-light);">
              <tr><td class="px-3 py-2.5 font-medium" style="color: var(--text-2);">NIST CPE</td><td class="px-3 py-2.5" style="color: var(--text-3);">Common Platform Enumeration database &mdash; vendor, product, version data</td></tr>
              <tr><td class="px-3 py-2.5 font-medium" style="color: var(--text-2);">MITRE ATT&CK</td><td class="px-3 py-2.5" style="color: var(--text-3);">Adversary techniques mapped to software tools</td></tr>
              <tr><td class="px-3 py-2.5 font-medium" style="color: var(--text-2);">Chocolatey</td><td class="px-3 py-2.5" style="color: var(--text-3);">Windows package repository &mdash; common enterprise software</td></tr>
              <tr><td class="px-3 py-2.5 font-medium" style="color: var(--text-2);">Homebrew</td><td class="px-3 py-2.5" style="color: var(--text-3);">macOS package repository</td></tr>
            </tbody>
          </table>
          <p class="text-[14px] leading-relaxed mb-5" style="color: var(--text-2);">
            Library entries are stored in the shared database and are visible to all tenants. You can also
            create manual entries for custom or internal software.
          </p>
          <router-link to="/library/sources" aria-label="Open Library Sources page" class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium transition-colors no-underline" style="background: var(--brand-primary); color: white;">Open Library Sources &rarr;</router-link>
        </section>

        <!-- ── Compliance Reports ────────────────────────────────────────── -->
        <section id="p-compliance" class="scroll-mt-4">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-8 h-8 rounded-xl flex items-center justify-center shrink-0" style="background: var(--scope-site-bg);">
              <svg aria-hidden="true" class="w-4 h-4" style="color: var(--scope-site-text);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <h2 class="text-[18px] font-bold" style="color: var(--heading);">Compliance Reports</h2>
          </div>
          <p class="text-[14px] leading-relaxed mb-4" style="color: var(--text-2);">
            Generate compliance reports for auditors with a single click. Each report snapshots the current
            control status and can be exported as CSV.
          </p>
          <ul class="space-y-2 mb-5 ml-1">
            <li class="flex gap-3 text-[14px]">
              <span class="shrink-0 mt-1 w-1.5 h-1.5 rounded-full" style="background: var(--scope-site-text);"></span>
              <div><span class="font-medium" style="color: var(--text-2);">SOC 2 Type II</span> <span style="color: var(--text-3);">&mdash; 8 controls covering access, auth, monitoring, change management, availability, risk, and communication.</span></div>
            </li>
            <li class="flex gap-3 text-[14px]">
              <span class="shrink-0 mt-1 w-1.5 h-1.5 rounded-full" style="background: var(--scope-site-text);"></span>
              <div><span class="font-medium" style="color: var(--text-2);">ISO 27001</span> <span style="color: var(--text-3);">&mdash; 6 controls covering organizational, people, physical, and technological security domains.</span></div>
            </li>
            <li class="flex gap-3 text-[14px]">
              <span class="shrink-0 mt-1 w-1.5 h-1.5 rounded-full" style="background: var(--scope-site-text);"></span>
              <div><span class="font-medium" style="color: var(--text-2);">Zero manual entry</span> <span style="color: var(--text-3);">&mdash; all evidence is collected from existing data stores (users, audit logs, backups, etc.).</span></div>
            </li>
          </ul>
          <router-link to="/compliance" aria-label="Open Compliance page" class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium transition-colors no-underline" style="background: var(--brand-primary); color: white;">Open Compliance &rarr;</router-link>
        </section>

        <!-- ── Webhooks ──────────────────────────────────────────────────── -->
        <section id="p-webhooks" class="scroll-mt-4">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-8 h-8 rounded-xl flex items-center justify-center shrink-0" style="background: var(--info-bg);">
              <svg aria-hidden="true" class="w-4 h-4" style="color: var(--info-text);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
            </div>
            <h2 class="text-[18px] font-bold" style="color: var(--heading);">Webhooks</h2>
          </div>
          <p class="text-[14px] leading-relaxed mb-4" style="color: var(--text-2);">
            Configure outbound webhooks to notify external systems when events occur &mdash; sync completions,
            classification results, anomaly detections, and more. Each webhook specifies a URL, event types,
            and optional secret for HMAC signature verification.
          </p>
          <router-link to="/webhooks" aria-label="Open Webhooks page" class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium transition-colors no-underline" style="background: var(--brand-primary); color: white;">Open Webhooks &rarr;</router-link>
        </section>

        <!-- ── Audit Log ─────────────────────────────────────────────────── -->
        <section id="p-audit" class="scroll-mt-4">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-8 h-8 rounded-xl flex items-center justify-center shrink-0" style="background: var(--badge-bg);">
              <svg aria-hidden="true" class="w-4 h-4" style="color: var(--badge-text);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
              </svg>
            </div>
            <h2 class="text-[18px] font-bold" style="color: var(--heading);">Audit Log</h2>
          </div>
          <p class="text-[14px] leading-relaxed mb-4" style="color: var(--text-2);">
            Every mutation is recorded in a structured JSON audit log with actor, timestamp, domain, action,
            and details. Use the audit log to investigate changes, track user activity, and satisfy compliance
            requirements for change documentation.
          </p>
          <p class="text-[14px] leading-relaxed mb-5" style="color: var(--text-2);">
            The audit log feeds directly into the SOC 2 CC7.2 (monitoring) and ISO 27001 A.8.15 (logging)
            compliance controls. Active logging is required for these controls to pass.
          </p>
          <router-link to="/audit" aria-label="Open Audit Log page" class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium transition-colors no-underline" style="background: var(--brand-primary); color: white;">Open Audit Log &rarr;</router-link>
        </section>

        <!-- ── Role Reference ────────────────────────────────────────────── -->
        <section id="p-roles" class="scroll-mt-4 pb-16">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-8 h-8 rounded-xl flex items-center justify-center shrink-0" style="background: var(--badge-bg);">
              <svg aria-hidden="true" class="w-4 h-4" style="color: var(--badge-text);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            </div>
            <h2 class="text-[18px] font-bold" style="color: var(--heading);">Role &amp; Permission Reference</h2>
          </div>

          <table class="w-full text-[13px] rounded-xl overflow-hidden" style="border: 1px solid var(--border);">
            <thead style="background: var(--surface-inset);">
              <tr>
                <th class="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Feature</th>
                <th class="px-3 py-2 text-center text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">viewer</th>
                <th class="px-3 py-2 text-center text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">analyst</th>
                <th class="px-3 py-2 text-center text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">admin</th>
                <th class="px-3 py-2 text-center text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">super_admin</th>
              </tr>
            </thead>
            <tbody class="divide-y" style="border-color: var(--border-light);">
              <tr v-for="row in [
                { feature: 'Browse data (dashboard, groups, agents, apps)', viewer: true, analyst: true, admin: true, sa: true },
                { feature: 'Create/edit fingerprints & proposals', viewer: false, analyst: true, admin: true, sa: true },
                { feature: 'Run classification', viewer: false, analyst: true, admin: true, sa: true },
                { feature: 'Subscribe to library entries', viewer: false, analyst: true, admin: true, sa: true },
                { feature: 'Create library entries', viewer: false, analyst: true, admin: true, sa: true },
                { feature: 'Publish/delete library entries', viewer: false, analyst: false, admin: true, sa: true },
                { feature: 'Manage users', viewer: false, analyst: false, admin: true, sa: true },
                { feature: 'Manage webhooks', viewer: false, analyst: false, admin: true, sa: true },
                { feature: 'View compliance & generate reports', viewer: false, analyst: false, admin: true, sa: true },
                { feature: 'Manage settings', viewer: false, analyst: false, admin: true, sa: true },
                { feature: 'Library sources & ingestion', viewer: false, analyst: false, admin: false, sa: true },
                { feature: 'Tenant management', viewer: false, analyst: false, admin: false, sa: true },
              ]" :key="row.feature">
                <td class="px-3 py-2.5" style="color: var(--text-2);">{{ row.feature }}</td>
                <td class="px-3 py-2.5 text-center">{{ row.viewer ? '\u2713' : '\u2014' }}</td>
                <td class="px-3 py-2.5 text-center">{{ row.analyst ? '\u2713' : '\u2014' }}</td>
                <td class="px-3 py-2.5 text-center">{{ row.admin ? '\u2713' : '\u2014' }}</td>
                <td class="px-3 py-2.5 text-center">{{ row.sa ? '\u2713' : '\u2014' }}</td>
              </tr>
            </tbody>
          </table>
        </section>

      </template>

    </div>
  </div>
</template>
