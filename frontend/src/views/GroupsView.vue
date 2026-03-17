<!--
  Groups view — hierarchy: Account → Sites → Groups.
  Sites shown as filter pills; groups filtered per site.
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import * as groupsApi from '@/api/groups'
import type { Site, Group } from '@/api/groups'

const router = useRouter()

const sites = ref<Site[]>([])
const groups = ref<Group[]>([])
const selectedSiteId = ref<string | null>(null)
const isLoading = ref(true)
const error = ref<string | null>(null)

const accountName = computed(() => sites.value[0]?.account_name ?? null)

const filteredGroups = computed(() =>
  selectedSiteId.value
    ? groups.value.filter((g) => g.site_id === selectedSiteId.value)
    : groups.value,
)

onMounted(async () => {
  try {
    const [sitesRes, groupsRes] = await Promise.all([
      groupsApi.listSites(),
      groupsApi.listGroups(),
    ])
    sites.value = sitesRes.sites
    groups.value = groupsRes.groups
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load data'
  } finally {
    isLoading.value = false
  }
})

function osChipClass(os: string): string {
  const lower = os.toLowerCase()
  if (lower === 'windows') return 'bg-[var(--info-bg)] text-[var(--info-text)] border-[var(--border)]'
  if (lower === 'linux') return 'bg-[var(--warn-bg)] text-[var(--warn-text)] border-[var(--warn-border)]'
  if (lower === 'macos') return 'badge-neutral border'
  return 'badge-neutral border'
}

function groupCountForSite(siteId: string): number {
  return groups.value.filter((g) => g.site_id === siteId).length
}
</script>

<template>
  <div class="p-6 max-w-[1200px] mx-auto">

    <!-- Header -->
    <div class="mb-5">
      <div class="flex items-baseline gap-2">
        <h1 class="text-[18px] font-bold" style="color: var(--heading);">Groups</h1>
        <span v-if="accountName" class="text-[12px]" style="color: var(--text-3);">· {{ accountName }}</span>
      </div>
      <p v-if="!isLoading && !error" class="text-[12px] mt-0.5" style="color: var(--text-3);">
        {{ filteredGroups.length }} group{{ filteredGroups.length !== 1 ? 's' : '' }}
        <template v-if="selectedSiteId">
          in {{ sites.find(s => s.source_id === selectedSiteId)?.name }}
        </template>
        <template v-else>across {{ sites.length }} site{{ sites.length !== 1 ? 's' : '' }}</template>
      </p>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="flex items-center justify-center py-24 text-[13px]" style="color: var(--text-3);" aria-live="polite" role="status">
      Loading…
    </div>

    <!-- Error -->
    <div v-else-if="error" class="flex items-center justify-center py-24 text-[var(--error-text)] text-[13px]">
      {{ error }}
    </div>

    <template v-else>
      <!-- Site filter pills -->
      <div v-if="sites.length" class="flex flex-wrap gap-2 mb-5">
        <button
          class="px-3 py-1.5 rounded-full text-[12px] font-medium transition-colors"
          :class="selectedSiteId === null
            ? 'bg-[var(--brand-primary)] border-indigo-600 text-white'
            : ''"
          :style="selectedSiteId === null ? 'border: 1px solid transparent;' : `background: var(--surface); border: 1px solid var(--border); color: var(--text-2);`"
          aria-label="Show all sites"
          :aria-pressed="selectedSiteId === null"
          @click="selectedSiteId = null"
        >
          All sites
          <span class="ml-1.5 opacity-70 tabular-nums">{{ groups.length }} groups</span>
        </button>
        <button
          v-for="site in sites"
          :key="site.source_id"
          class="px-3 py-1.5 rounded-full text-[12px] font-medium transition-colors"
          :class="selectedSiteId === site.source_id
            ? 'bg-[var(--brand-primary)] border-indigo-600 text-white'
            : ''"
          :style="selectedSiteId === site.source_id ? 'border: 1px solid transparent;' : `background: var(--surface); border: 1px solid var(--border); color: var(--text-2);`"
          :aria-label="`Filter by site ${site.name}`"
          :aria-pressed="selectedSiteId === site.source_id"
          @click="selectedSiteId = site.source_id"
        >
          {{ site.name }}
          <span class="ml-1.5 opacity-70 tabular-nums">{{ groupCountForSite(site.source_id) }} groups</span>
        </button>
      </div>

      <!-- Empty state -->
      <div
        v-if="!filteredGroups.length"
        class="flex flex-col items-center justify-center py-24 gap-4"
        style="color: var(--text-3);"
      >
        <svg class="w-12 h-12 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
        <p class="text-[14px] font-medium" style="color: var(--text-3);">No groups yet</p>
        <p class="text-[12px]">Sync your data to see groups here.</p>
        <router-link
          to="/sync"
          class="mt-2 px-4 py-2 rounded-lg bg-[var(--brand-primary)] hover:opacity-90 text-white text-[13px] font-medium transition-colors no-underline"
        >
          Go to Sync
        </router-link>
      </div>

      <!-- Group cards grid -->
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div
          v-for="group in filteredGroups"
          :key="group.group_id"
          class="rounded-xl p-5 hover:border-[var(--border)] hover:shadow-md transition-all cursor-pointer"
          style="background: var(--surface); border: 1px solid var(--border);"
          role="button"
          tabindex="0"
          :aria-label="`Group ${group.group_name ?? group.group_id}, ${group.agent_count} agent${group.agent_count !== 1 ? 's' : ''}, ${group.has_fingerprint ? 'has fingerprint' : 'no fingerprint'}`"
          @click="router.push(`/fingerprints/${group.group_id}`)"
          @keydown.enter="router.push(`/fingerprints/${group.group_id}`)"
        >
          <!-- Top row: name + fingerprint dot -->
          <div class="flex items-start justify-between gap-2 mb-1">
            <div class="min-w-0">
              <h2 class="text-[14px] font-semibold leading-snug break-words" style="color: var(--heading);">
                {{ group.group_name ?? group.group_id }}
              </h2>
              <p class="text-[10px] text-[var(--text-3)] font-mono mt-0.5 truncate">{{ group.group_id }}</p>
            </div>
            <div class="flex items-center gap-1 shrink-0 mt-0.5">
              <span
                class="w-2 h-2 rounded-full"
                :class="group.has_fingerprint ? 'bg-[var(--status-ok-text)]' : 'bg-[var(--text-3)]'"
              />
              <span
                class="text-[11px]"
                :class="group.has_fingerprint ? 'text-[var(--success-text)]' : ''"
                :style="group.has_fingerprint ? '' : 'color: var(--text-3);'"
              >
                {{ group.has_fingerprint ? 'Fingerprint' : 'No fingerprint' }}
              </span>
            </div>
          </div>

          <!-- Site name (shown when All is selected) -->
          <p v-if="!selectedSiteId && group.site_name" class="text-[11px] mb-2" style="color: var(--text-3);">
            {{ group.site_name }}
          </p>

          <!-- Description -->
          <p v-if="group.description" class="text-[12px] mb-2 leading-snug" style="color: var(--text-3);">
            {{ group.description }}
          </p>

          <!-- Type / Default badges -->
          <div class="flex flex-wrap gap-1.5 mb-2">
            <span
              v-if="group.is_default"
              class="text-[10px] font-medium px-1.5 py-0.5 rounded" style="background: var(--badge-bg); color: var(--badge-text);"
            >Default</span>
            <span
              v-if="group.type === 'dynamic'"
              class="text-[10px] font-medium px-1.5 py-0.5 rounded bg-purple-50 text-purple-500"
            >Dynamic</span>
            <span
              v-if="group.filter_name"
              class="text-[10px] truncate max-w-[160px]"
              style="color: var(--text-3);"
              :title="group.filter_name"
            >Filter: {{ group.filter_name }}</span>
          </div>

          <!-- Agent count -->
          <div class="flex items-center gap-1.5 mb-3">
            <svg class="w-3.5 h-3.5 shrink-0" style="color: var(--text-3);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span class="text-[12px] font-medium" style="color: var(--text-2);">
              {{ group.agent_count }} agent{{ group.agent_count !== 1 ? 's' : '' }}
            </span>
          </div>

          <!-- OS type chips -->
          <div v-if="group.os_types.length" class="flex flex-wrap gap-1.5">
            <span
              v-for="os in group.os_types"
              :key="os"
              class="text-[11px] font-medium px-2 py-0.5 rounded-full border"
              :class="osChipClass(os)"
            >
              {{ os }}
            </span>
          </div>
        </div>
      </div>
    </template>

  </div>
</template>
