<!--
  Agent detail view — deep dive for a single agent.
  Shows hostname, OS, IPs, group, agent status, match score breakdown,
  and the full installed applications list.
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as agentsApi from '@/api/agents'
import type { AgentDetailResponse } from '@/types/agent'
import { formatDateTime } from '@/utils/formatters'

const route = useRoute()
const router = useRouter()
const agent = ref<AgentDetailResponse | null>(null)
const isLoading = ref(true)
const error = ref<string | null>(null)
const appSearch = ref('')

type AppSortCol = 'name' | 'publisher' | 'installed_at'
const appSort = ref<AppSortCol>('name')
const appSortDir = ref<'asc' | 'desc'>('asc')

function toggleAppSort(col: AppSortCol) {
  if (appSort.value === col) {
    appSortDir.value = appSortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    appSort.value = col
    appSortDir.value = col === 'installed_at' ? 'desc' : 'asc'
  }
}

function appSortIcon(col: AppSortCol): string {
  if (appSort.value !== col) return '↕'
  return appSortDir.value === 'asc' ? '↑' : '↓'
}

async function loadAgent() {
  isLoading.value = true
  error.value = null
  agent.value = null
  try {
    agent.value = await agentsApi.getAgent(route.params.agentId as string)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load agent'
  } finally {
    isLoading.value = false
  }
}

onMounted(loadAgent)

watch(() => route.params.agentId, (newId, oldId) => {
  if (newId && newId !== oldId) loadAgent()
})

const filteredApps = computed(() => {
  if (!agent.value?.installed_apps) return []
  let list = agent.value.installed_apps
  const q = appSearch.value.trim().toLowerCase()
  if (q) list = list.filter(
    (a) => a.name.toLowerCase().includes(q) || (a.publisher ?? '').toLowerCase().includes(q),
  )

  return [...list].sort((a, b) => {
    const dir = appSortDir.value === 'asc' ? 1 : -1
    if (appSort.value === 'installed_at') {
      const av = a.installed_at ? new Date(a.installed_at).getTime() : 0
      const bv = b.installed_at ? new Date(b.installed_at).getTime() : 0
      return (av - bv) * dir
    }
    const av = (appSort.value === 'publisher' ? (a.publisher ?? '') : a.name).toLowerCase()
    const bv = (appSort.value === 'publisher' ? (b.publisher ?? '') : b.name).toLowerCase()
    return av.localeCompare(bv) * dir
  })
})

/** Collect all matched marker strings across all match scores for highlight use. */
const allMatchedMarkers = computed<string[]>(() => {
  if (!agent.value?.classification?.match_scores) return []
  return agent.value.classification.match_scores.flatMap((ms) => ms.matched_markers)
})

function isAppHighlighted(appName: string): boolean {
  const lower = appName.toLowerCase()
  return allMatchedMarkers.value.some((marker) => lower.includes(marker.toLowerCase()))
}

/** Find the group match score with the highest score value. */
const bestMatchGroupId = computed<string | null>(() => {
  const scores = agent.value?.classification?.match_scores
  if (!scores || scores.length === 0) return null
  return scores.reduce((best, cur) => (cur.score > best.score ? cur : best)).group_id
})
</script>

<template>
  <div class="p-6 max-w-[900px] space-y-5">

    <router-link
      to="/anomalies"
      aria-label="Back to Anomalies"
      class="inline-flex items-center gap-1.5 text-[13px] text-[var(--info-text)] hover:text-[var(--heading)] no-underline font-medium"
    >
      <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" />
      </svg>
      Back to Anomalies
    </router-link>

    <!-- Loading -->
    <div v-if="isLoading" class="flex items-center justify-center py-24 text-[13px]" style="color: var(--text-3);">
      Loading…
    </div>

    <!-- Error -->
    <div v-else-if="error" class="flex items-center justify-center py-24 text-[var(--error-text)] text-[13px]">
      {{ error }}
    </div>

    <!-- Agent detail -->
    <template v-else-if="agent">

      <!-- Header card -->
      <div class="rounded-xl px-6 py-5" style="background: var(--surface); border: 1px solid var(--border);">
        <h1 class="text-[20px] font-bold mb-3" style="color: var(--heading);">{{ agent.hostname }}</h1>
        <div class="flex flex-wrap gap-4">
          <div class="flex items-center gap-1.5 text-[12px]" style="color: var(--text-3);">
            <svg class="w-3.5 h-3.5" style="color: var(--text-3);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            {{ agent.os_type }} {{ agent.os_version }}
          </div>
          <div class="flex items-center gap-1.5 text-[12px]" style="color: var(--text-3);">
            <svg class="w-3.5 h-3.5" style="color: var(--text-3);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
            {{ agent.group_name }}
          </div>
          <div class="flex items-center gap-1.5 text-[12px]" style="color: var(--text-3);">
            <span
              class="w-2 h-2 rounded-full"
              :class="agent.agent_status === 'online' ? 'bg-[var(--status-ok-text)]' : 'bg-[var(--text-3)]'"
            />
            {{ agent.agent_status }}
          </div>
          <div class="flex items-center gap-1.5 text-[12px]" style="color: var(--text-3);">
            Last active: {{ formatDateTime(agent.last_active) }}
          </div>
        </div>
      </div>

      <!-- Match scores -->
      <div class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
        <div class="px-5 py-4" style="border-bottom: 1px solid var(--border-light);">
          <h2 class="text-[14px] font-semibold" style="color: var(--heading);">Match Scores</h2>
        </div>

        <!-- No classification data -->
        <div
          v-if="!agent.classification?.match_scores?.length"
          class="px-5 py-6 text-[13px] italic"
          style="color: var(--text-3);"
        >
          No classification data available for this agent.
        </div>

        <!-- Score list -->
        <div v-else class="divide-y" style="--tw-divide-opacity: 1; border-color: var(--border-light);">
          <div
            v-for="ms in agent.classification!.match_scores"
            :key="ms.group_id"
            class="px-5 py-4 space-y-2.5"
            :class="ms.group_id === agent.group_id ? 'bg-[var(--info-bg)]/40' : ''"
            :style="`border-bottom: 1px solid var(--border-light);`"
          >
            <!-- Group name row -->
            <div class="flex items-center justify-between gap-3">
              <div class="flex items-center gap-2">
                <span
                  class="text-[13px] font-semibold"
                  :class="ms.group_id === agent.group_id ? 'text-[var(--info-text)]' : ''"
                  :style="ms.group_id === agent.group_id ? '' : `color: var(--heading);`"
                >
                  {{ ms.group_name }}
                </span>
                <span
                  v-if="ms.group_id === agent.group_id"
                  class="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-[var(--info-bg)] text-[var(--info-text)]"
                >
                  Current group
                </span>
              </div>
              <div class="flex items-center gap-2">
                <!-- Best match badge -->
                <span
                  v-if="ms.group_id === bestMatchGroupId"
                  class="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-[var(--success-bg)] text-[var(--success-text)]"
                >
                  Best match
                </span>
                <span class="text-[13px] font-semibold tabular-nums" style="color: var(--text-2);">
                  {{ Math.round(ms.score * 100) }}%
                </span>
              </div>
            </div>

            <!-- Progress bar -->
            <div class="h-[6px] rounded-full  overflow-hidden" style="background: var(--surface-hover);">
              <div
                role="progressbar"
                :aria-valuenow="Math.round(ms.score * 100)"
                aria-valuemin="0"
                aria-valuemax="100"
                :aria-label="`Match score for ${ms.group_name}: ${Math.round(ms.score * 100)}%`"
                class="h-full rounded-full transition-all duration-500"
                :class="ms.group_id === bestMatchGroupId ? 'bg-[var(--success-bg)]0' : 'bg-[var(--brand-primary)]'"
                :style="{ width: `${Math.round(ms.score * 100)}%` }"
              />
            </div>

            <!-- Markers -->
            <div v-if="ms.matched_markers.length || ms.missing_markers.length" class="flex flex-wrap gap-1.5">
              <span
                v-for="marker in ms.matched_markers"
                :key="`matched-${marker}`"
                class="text-[11px] font-medium px-2 py-0.5 rounded-full bg-[var(--success-bg)] text-[var(--success-text)] border border-[var(--success-border)]"
              >
                {{ marker }}
              </span>
              <span
                v-for="marker in ms.missing_markers"
                :key="`missing-${marker}`"
                class="text-[11px] font-medium px-2 py-0.5 rounded-full  text-[var(--text-3)] border border-slate-200" style="background: var(--surface-hover);"
              >
                {{ marker }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Installed apps -->
      <div class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
        <div class="px-5 py-4 flex items-center justify-between gap-4" style="border-bottom: 1px solid var(--border-light);">
          <h2 class="text-[14px] font-semibold shrink-0" style="color: var(--heading);">
            Installed Applications
            <span class="ml-2 text-[12px] font-normal" style="color: var(--text-3);">
              ({{ filteredApps.length }}{{ appSearch.trim() ? ` of ${agent.installed_apps?.length ?? 0}` : '' }})
            </span>
          </h2>
          <!-- Search -->
          <input
            v-model="appSearch"
            type="text"
            aria-label="Search installed applications by name or publisher"
            placeholder="Search by name or publisher…"
            class="w-56 text-[12px] px-3 py-1.5 rounded-lg placeholder-[var(--text-3)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-primary-light)] transition"
            style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
          />
        </div>

        <!-- Empty state -->
        <div v-if="!filteredApps.length" class="px-5 py-8 text-center text-[13px] italic" style="color: var(--text-3);">
          {{ appSearch.trim() ? 'No applications match your search.' : 'No installed applications recorded.' }}
        </div>

        <!-- Apps table -->
        <div v-else class="overflow-x-auto" aria-live="polite">
          <table class="w-full text-[12px]">
            <thead>
              <tr style="border-bottom: 1px solid var(--border-light); background: var(--surface-inset);">
                <th scope="col" :aria-sort="appSort === 'name' ? (appSortDir === 'asc' ? 'ascending' : 'descending') : 'none'" class="text-left px-5 py-2.5 font-semibold w-[38%]" style="color: var(--text-3);">
                  <button class="flex items-center gap-1 transition-colors" @click="toggleAppSort('name')">
                    Name <span class="font-mono text-[10px]">{{ appSortIcon('name') }}</span>
                  </button>
                </th>
                <th scope="col" :aria-sort="appSort === 'publisher' ? (appSortDir === 'asc' ? 'ascending' : 'descending') : 'none'" class="text-left px-4 py-2.5 font-semibold w-[25%]" style="color: var(--text-3);">
                  <button class="flex items-center gap-1 transition-colors" @click="toggleAppSort('publisher')">
                    Publisher <span class="font-mono text-[10px]">{{ appSortIcon('publisher') }}</span>
                  </button>
                </th>
                <th scope="col" class="text-left px-4 py-2.5 font-semibold w-[15%]" style="color: var(--text-3);">Version</th>
                <th scope="col" :aria-sort="appSort === 'installed_at' ? (appSortDir === 'asc' ? 'ascending' : 'descending') : 'none'" class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-3);">
                  <button class="flex items-center gap-1 transition-colors" @click="toggleAppSort('installed_at')">
                    Installed <span class="font-mono text-[10px]">{{ appSortIcon('installed_at') }}</span>
                  </button>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="app in filteredApps"
                :key="app.name + (app.version ?? '')"
                class="transition-colors"
                :class="isAppHighlighted(app.name) ? 'bg-[var(--success-bg)]/40' : ''"
                style="border-bottom: 1px solid var(--border-light);"
              >
                <td class="px-5 py-2.5 font-medium truncate max-w-[280px]" style="color: var(--heading);">
                  <span
                    v-if="isAppHighlighted(app.name)"
                    class="inline-block w-1.5 h-1.5 rounded-full bg-[var(--status-ok-text)] mr-1.5 align-middle"
                  />
                  <button
                    class="hover:text-[var(--info-text)] hover:underline transition-colors text-left truncate"
                    @click.stop="router.push({ name: 'app-detail', params: { normalizedName: app.normalized_name } })"
                  >{{ app.name }}</button>
                </td>
                <td class="px-4 py-2.5 truncate max-w-[200px]" style="color: var(--text-3);">
                  {{ app.publisher ?? '—' }}
                </td>
                <td class="px-4 py-2.5 font-mono" style="color: var(--text-3);">
                  {{ app.version ?? '—' }}
                </td>
                <td class="px-4 py-2.5" style="color: var(--text-3);">
                  {{ app.installed_at ? formatDateTime(app.installed_at) : '—' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

    </template>
  </div>
</template>
