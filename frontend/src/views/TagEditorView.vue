<!--
  Tag Management — professional asset tag management UI.
  Left sidebar: S1 tags overview + tag rules list (searchable).
  Main area: Three-panel editor (catalog | patterns | preview) when a rule is active.
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTagStore } from '@/stores/useTagStore'
import { useTaxonomyStore } from '@/stores/useTaxonomyStore'
import type { SoftwareEntry, PatternPreviewResponse } from '@/types/taxonomy'
import type { TagRulePattern, S1Tag } from '@/types/tags'
import * as taxonomyApi from '@/api/taxonomy'
import * as tagsApi from '@/api/tags'

const route = useRoute()
const router = useRouter()
const tagStore = useTagStore()
const taxStore = useTaxonomyStore()

// ── S1 Tags state ──────────────────────────────────────────────────────────────
const s1Tags = ref<S1Tag[]>([])
const s1TagsLoading = ref(false)
const s1TagSearch = ref('')

// ── Route + active state ───────────────────────────────────────────────────────
const ruleId = computed(() => (route.params.ruleId as string) || '')
const expandedCategory = ref<string | null>(null)
const isDragOver = ref(false)
const catalogSearch = ref('')

// Pattern selection + preview
const selectedPatternId = ref<string | null>(null)
const patternPreview = ref<PatternPreviewResponse | null>(null)
const isLoadingPreview = ref(false)

// New rule form
const showNewRuleForm = ref(false)
const newTagName = ref('')
const newDescription = ref('')
const isCreating = ref(false)
const createError = ref<string | null>(null)

// Inline tag_name editing
const isEditingName = ref(false)
const editingName = ref('')

// Right panel mode
const rightPanelMode = ref<'pattern' | 'agents'>('pattern')

// ── Sidebar mode: 's1tags' or 'rules' ─────────────────────────────────────────
const sidebarTab = ref<'s1tags' | 'rules'>('s1tags')

// ── Lifecycle ──────────────────────────────────────────────────────────────────
onMounted(async () => {
  await Promise.all([
    taxStore.fetchCategories(),
    tagStore.fetchRules(),
    loadS1Tags(),
  ])
  if (ruleId.value) {
    await tagStore.loadRule(ruleId.value)
  }
})

async function loadS1Tags() {
  s1TagsLoading.value = true
  try {
    const resp = await tagsApi.listSyncedTags()
    s1Tags.value = resp.tags
  } catch {
    s1Tags.value = []
  } finally {
    s1TagsLoading.value = false
  }
}

watch(
  () => ruleId.value,
  async (id) => {
    isDragOver.value = false
    expandedCategory.value = null
    selectedPatternId.value = null
    patternPreview.value = null
    rightPanelMode.value = 'pattern'
    if (id) {
      await tagStore.loadRule(id)
    } else {
      tagStore.activeRule = null
      tagStore.previewResult = null
    }
  },
)

// ── S1 Tags computed ───────────────────────────────────────────────────────────

/** Unique tag names with their scopes and whether a rule exists */
const s1TagGroups = computed(() => {
  const q = s1TagSearch.value.toLowerCase().trim()
  const tagsByName = new Map<string, { name: string; tags: S1Tag[]; rule: typeof tagStore.rules.value extends (infer T)[] ? T : never | null }>()

  for (const tag of s1Tags.value) {
    if (q && !tag.name.toLowerCase().includes(q)) continue
    if (!tagsByName.has(tag.name)) {
      const matchingRule = tagStore.rules.find((r) => r.tag_name === tag.name) ?? null
      tagsByName.set(tag.name, { name: tag.name, tags: [], rule: matchingRule })
    }
    tagsByName.get(tag.name)!.tags.push(tag)
  }

  return Array.from(tagsByName.values()).sort((a, b) => a.name.localeCompare(b.name))
})

/** Rules not linked to any S1 tag */
const orphanRules = computed(() => {
  const s1Names = new Set(s1Tags.value.map((t) => t.name))
  return tagStore.rules.filter((r) => !s1Names.has(r.tag_name))
})

const filteredRules = computed(() => {
  const q = s1TagSearch.value.toLowerCase().trim()
  if (!q) return tagStore.rules
  return tagStore.rules.filter(
    (r) => r.tag_name.toLowerCase().includes(q) || r.description.toLowerCase().includes(q),
  )
})

// ── S1 Tag actions ─────────────────────────────────────────────────────────────

async function openTagRule(tagKey: string) {
  const existing = tagStore.rules.find((r) => r.tag_name === tagKey)
  if (existing) {
    router.push({ name: 'tag-editor', params: { ruleId: existing.id } })
    return
  }
  // Auto-create the rule and navigate directly to the three-panel editor
  isCreating.value = true
  createError.value = null
  try {
    const rule = await tagStore.createRule({ tag_name: tagKey, description: '' })
    if (rule) {
      sidebarTab.value = 'rules'
      await router.push({ name: 'tag-editor', params: { ruleId: rule.id } })
    }
  } catch (err) {
    // Fall back to showing the new rule form if creation fails
    newTagName.value = tagKey
    newDescription.value = ''
    showNewRuleForm.value = true
    sidebarTab.value = 'rules'
    createError.value = err instanceof Error ? err.message : 'Failed to create rule'
  } finally {
    isCreating.value = false
  }
}

function openRule(id: string) {
  router.push({ name: 'tag-editor', params: { ruleId: id } })
}

// ── Catalog ────────────────────────────────────────────────────────────────────

const catalogSearchResults = ref<SoftwareEntry[]>([])
const isCatalogSearching = ref(false)
let catalogSearchTimer: ReturnType<typeof setTimeout> | null = null

/** When catalogSearch changes, debounce an API search for entries */
watch(catalogSearch, (q) => {
  if (catalogSearchTimer) clearTimeout(catalogSearchTimer)
  if (!q.trim()) {
    catalogSearchResults.value = []
    return
  }
  catalogSearchTimer = setTimeout(async () => {
    isCatalogSearching.value = true
    try {
      const resp = await taxonomyApi.searchTaxonomy(q.trim(), 40)
      catalogSearchResults.value = resp.entries
    } catch {
      catalogSearchResults.value = []
    } finally {
      isCatalogSearching.value = false
    }
  }, 250)
})

const hasCatalogSearch = computed(() => catalogSearch.value.trim().length > 0)

const filteredCategories = computed(() => {
  if (!catalogSearch.value.trim()) return taxStore.categories
  const q = catalogSearch.value.toLowerCase()
  // Show categories that match by name OR have matching entries in search results
  const matchedCategoryKeys = new Set(catalogSearchResults.value.map((e) => e.category))
  return taxStore.categories.filter(
    (c) => c.display.toLowerCase().includes(q) || matchedCategoryKeys.has(c.key),
  )
})

async function toggleCategory(key: string) {
  if (expandedCategory.value === key) {
    expandedCategory.value = null
    return
  }
  expandedCategory.value = key
  await taxStore.fetchEntriesByCategory(key)
}

function onDragStart(e: DragEvent, entry: SoftwareEntry) {
  const pattern = entry.patterns[0] ?? entry.name.toLowerCase().replace(/\s+/g, '_')
  e.dataTransfer?.setData(
    'application/json',
    JSON.stringify({ pattern, display_name: entry.name, category: entry.category }),
  )
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'copy'
}

// ── Drop zone ──────────────────────────────────────────────────────────────────

function onDragOver(e: DragEvent) {
  e.preventDefault()
  isDragOver.value = true
}

function onDragLeave(e: DragEvent) {
  const t = e.currentTarget as HTMLElement
  if (!t.contains(e.relatedTarget as Node)) isDragOver.value = false
}

async function onDrop(e: DragEvent) {
  e.preventDefault()
  isDragOver.value = false
  const raw = e.dataTransfer?.getData('application/json')
  if (!raw) return
  try {
    const p = JSON.parse(raw) as { pattern: string; display_name: string; category: string }
    await addPatternPayload(p)
  } catch {
    /* ignore malformed drag data */
  }
}

async function addPatternPayload(p: {
  pattern: string
  display_name: string
  category: string
}) {
  if (!ruleId.value) return
  await tagStore.addPattern(ruleId.value, {
    pattern: p.pattern,
    display_name: p.display_name,
    category: p.category,
    source: 'manual',
  })
}

async function addEntryAsPattern(entry: SoftwareEntry) {
  await addPatternPayload({
    pattern: entry.patterns[0] ?? entry.name.toLowerCase().replace(/\s+/g, '_'),
    display_name: entry.name,
    category: entry.category,
  })
}

// ── Pattern management ─────────────────────────────────────────────────────────

const patterns = computed(() => tagStore.activeRule?.patterns ?? [])
const hasPatterns = computed(() => patterns.value.length > 0)

const selectedPattern = computed(
  () => patterns.value.find((p) => p.id === selectedPatternId.value) ?? null,
)

async function removePattern(patternId: string) {
  if (!ruleId.value) return
  if (selectedPatternId.value === patternId) {
    selectedPatternId.value = null
    patternPreview.value = null
  }
  await tagStore.removePattern(ruleId.value, patternId)
}

async function selectPattern(pattern: TagRulePattern) {
  if (selectedPatternId.value === pattern.id) {
    selectedPatternId.value = null
    patternPreview.value = null
    return
  }
  selectedPatternId.value = pattern.id
  rightPanelMode.value = 'pattern'
  isLoadingPreview.value = true
  patternPreview.value = null
  try {
    patternPreview.value = await taxonomyApi.previewPattern({
      pattern: pattern.pattern,
    })
  } catch {
    patternPreview.value = null
  } finally {
    isLoadingPreview.value = false
  }
}

// ── Inline name editing ────────────────────────────────────────────────────────

function startEditName() {
  editingName.value = tagStore.activeRule?.tag_name ?? ''
  isEditingName.value = true
}

async function commitName() {
  isEditingName.value = false
  if (!ruleId.value || !editingName.value.trim()) return
  if (editingName.value === tagStore.activeRule?.tag_name) return
  await tagStore.updateRule(ruleId.value, { tag_name: editingName.value.trim() })
}

// ── Actions ────────────────────────────────────────────────────────────────────

async function runPreview() {
  if (!ruleId.value) return
  selectedPatternId.value = null
  patternPreview.value = null
  rightPanelMode.value = 'agents'
  await tagStore.previewRule(ruleId.value)
}

async function runApply() {
  if (!ruleId.value) return
  if (patterns.value.length === 0) return
  await tagStore.applyRule(ruleId.value)
}

// ── Create rule ────────────────────────────────────────────────────────────────

async function submitNewRule() {
  if (!newTagName.value.trim()) return
  isCreating.value = true
  createError.value = null
  try {
    const rule = await tagStore.createRule({
      tag_name: newTagName.value.trim(),
      description: newDescription.value.trim(),
    })
    if (rule) {
      showNewRuleForm.value = false
      newTagName.value = ''
      newDescription.value = ''
      await router.push({ name: 'tag-editor', params: { ruleId: rule.id } })
    }
  } catch (err) {
    createError.value = err instanceof Error ? err.message : 'Failed to create rule'
  } finally {
    isCreating.value = false
  }
}

async function deleteActiveRule() {
  if (!ruleId.value) return
  await tagStore.deleteRule(ruleId.value)
  await router.push({ name: 'tags' })
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function applyStatusStyle(status: string): string {
  if (status === 'running') return 'background: var(--status-warn-bg); color: var(--status-warn-text);'
  if (status === 'done') return 'background: var(--status-ok-bg); color: var(--status-ok-text);'
  if (status === 'failed') return 'background: var(--status-error-bg); color: var(--status-error-text);'
  return 'background: var(--status-neutral-bg); color: var(--status-neutral-text);'
}

function applyStatusLabel(status: string): string {
  if (status === 'running') return 'Applying…'
  if (status === 'done') return 'Applied'
  if (status === 'failed') return 'Failed'
  return 'Idle'
}

function sourceStyle(source: string): string {
  return source === 'seed'
    ? 'background: var(--status-ok-bg); color: var(--status-ok-text);'
    : 'background: var(--info-bg); color: var(--info-text);'
}

function scopeLabel(scope: string): string {
  if (scope === 'site') return 'Site'
  if (scope === 'group') return 'Group'
  if (scope === 'account') return 'Account'
  if (scope === 'global') return 'Global'
  return scope
}

function scopeStyle(scope: string): string {
  if (scope === 'account' || scope === 'global') return 'background: var(--scope-account-bg); color: var(--scope-account-text);'
  if (scope === 'site') return 'background: var(--scope-site-bg); color: var(--scope-site-text);'
  if (scope === 'group') return 'background: var(--scope-group-bg); color: var(--scope-group-text);'
  return 'background: var(--status-neutral-bg); color: var(--status-neutral-text);'
}

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}
</script>

<template>
  <div class="flex h-full overflow-hidden">

    <!-- ═══════════════════════════════════════════════════════════════════════
         LEFT SIDEBAR — S1 Tags + Rules
         ═══════════════════════════════════════════════════════════════════════ -->
    <div class="w-[260px] shrink-0 flex flex-col overflow-hidden" style="border-right: 1px solid var(--border); background: var(--surface-alt);">

      <!-- Sidebar header: tabs -->
      <div class="shrink-0" style="border-bottom: 1px solid var(--border); background: var(--surface);">
        <div class="flex">
          <button
            class="flex-1 px-3 py-2.5 text-[11px] font-semibold uppercase tracking-widest transition-colors border-b-2 border-violet-500"
            :style="sidebarTab === 's1tags'
              ? 'color: var(--heading); background: var(--surface-hover);'
              : 'color: var(--text-3); border-color: transparent;'"
            @click="sidebarTab = 's1tags'"
          >
            S1 Tags
            <span
              v-if="s1Tags.length > 0"
              class="ml-1 text-[10px] font-medium px-1.5 py-0.5 rounded-full"
              style="background: var(--badge-bg); color: var(--badge-text);"
            >{{ s1Tags.length }}</span>
          </button>
          <button
            class="flex-1 px-3 py-2.5 text-[11px] font-semibold uppercase tracking-widest transition-colors border-b-2 border-violet-500"
            :style="sidebarTab === 'rules'
              ? 'color: var(--heading); background: var(--surface-hover);'
              : 'color: var(--text-3); border-color: transparent;'"
            @click="sidebarTab = 'rules'"
          >
            Rules
            <span
              v-if="tagStore.rules.length > 0"
              class="ml-1 text-[10px] font-medium px-1.5 py-0.5 rounded-full"
              style="background: var(--badge-bg); color: var(--badge-text);"
            >{{ tagStore.rules.length }}</span>
          </button>
        </div>
      </div>

      <!-- Search -->
      <div class="shrink-0 px-3 py-2.5" style="border-bottom: 1px solid var(--border);">
        <input
          v-model="s1TagSearch"
          type="text"
          :placeholder="sidebarTab === 's1tags' ? 'Search tags…' : 'Search rules…'"
          class="w-full text-[12px] px-2.5 py-1.5 rounded-md focus:outline-none focus:ring-1 focus:ring-violet-400 placeholder:text-[var(--text-3)]"
          style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
        />
      </div>

      <!-- ── S1 Tags tab ─────────────────────────────────────────────────────── -->
      <div v-if="sidebarTab === 's1tags'" class="flex-1 overflow-y-auto">

        <!-- Loading -->
        <div v-if="s1TagsLoading" class="px-4 py-6 text-center">
          <svg class="w-5 h-5 animate-spin mx-auto mb-2" style="color: var(--accent-text);" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <p class="text-[11px]" style="color: var(--text-3);">Loading S1 tags…</p>
        </div>

        <!-- Empty state -->
        <div v-else-if="s1Tags.length === 0" class="px-4 py-10 text-center">
          <svg class="w-8 h-8 mx-auto mb-2" style="color: var(--text-3); opacity: 0.5;" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
          </svg>
          <p class="text-[12px]" style="color: var(--text-3);">No S1 tags synced</p>
          <p class="text-[11px] mt-1" style="color: var(--text-3); opacity: 0.6;">Run a sync to fetch tags from SentinelOne</p>
        </div>

        <!-- S1 Tag groups (by key) -->
        <div v-else>
          <div
            v-for="group in s1TagGroups"
            :key="group.name"
            style="border-bottom: 1px solid var(--border-light);"
          >
            <button
              class="w-full flex items-center gap-2.5 px-3 py-2.5 transition-colors text-left group"
              @click="openTagRule(group.name)"
            >
              <!-- Tag icon -->
              <div class="flex items-center justify-center w-6 h-6 rounded-md shrink-0"
                :style="group.rule ? 'background: var(--accent-muted);' : 'background: var(--badge-bg);'"
              >
                <svg class="w-3.5 h-3.5" :style="group.rule ? 'color: var(--accent-text);' : 'color: var(--text-3);'" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                </svg>
              </div>

              <!-- Tag info -->
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-1.5">
                  <span class="text-[12px] font-medium truncate" style="color: var(--heading);">{{ group.name }}</span>
                  <span
                    v-if="group.rule"
                    class="shrink-0 text-[9px] font-semibold px-1.5 py-0.5 rounded-full"
                    style="background: var(--accent-muted); color: var(--accent-text);"
                  >RULE</span>
                </div>
                <div class="flex items-center gap-1.5 mt-0.5">
                  <span
                    v-for="scope in [...new Set(group.tags.map(t => t.scope))]"
                    :key="scope"
                    class="text-[9px] font-medium px-1 py-0 rounded"
                    :style="scopeStyle(scope)"
                  >{{ scopeLabel(scope) }}</span>
                  <span class="text-[10px]" style="color: var(--text-3);">{{ group.tags.length }} scope{{ group.tags.length !== 1 ? 's' : '' }}</span>
                </div>
              </div>

              <!-- Arrow / create hint -->
              <div class="shrink-0 flex items-center">
                <span
                  v-if="!group.rule"
                  class="text-[10px] opacity-0 group-hover:opacity-100 transition-opacity mr-1"
                  style="color: var(--accent-text);"
                >Create</span>
                <svg class="w-3.5 h-3.5 transition-colors" style="color: var(--text-3);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
                </svg>
              </div>
            </button>
          </div>
        </div>
      </div>

      <!-- ── Rules tab ───────────────────────────────────────────────────────── -->
      <div v-else class="flex-1 overflow-y-auto">

        <!-- New Rule button -->
        <div class="px-3 py-2.5" style="border-bottom: 1px solid var(--border-light);">
          <button
            class="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 text-[12px] font-medium bg-violet-600 text-white rounded-lg hover:bg-violet-700 transition-colors"
            @click="showNewRuleForm = !showNewRuleForm"
          >
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            New Rule
          </button>
        </div>

        <!-- New rule form (inline) -->
        <form
          v-if="showNewRuleForm"
          class="mx-3 my-2.5 p-3 rounded-lg"
          style="background: var(--surface-hover); border: 1px solid var(--border);"
          @submit.prevent="submitNewRule"
        >
          <div class="mb-2">
            <label class="block text-[10px] mb-0.5" style="color: var(--text-3);">Tag name (S1 tag key)</label>
            <input
              v-model="newTagName"
              type="text"
              placeholder="e.g. manufacturing"
              class="w-full text-[12px] px-2 py-1.5 rounded-md focus:outline-none focus:ring-1 focus:ring-violet-400"
              style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);"
              required
            />
          </div>
          <div class="mb-2.5">
            <label class="block text-[10px] mb-0.5" style="color: var(--text-3);">Description</label>
            <input
              v-model="newDescription"
              type="text"
              placeholder="When this tag applies"
              class="w-full text-[12px] px-2 py-1.5 rounded-md focus:outline-none focus:ring-1 focus:ring-violet-400"
              style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);"
            />
          </div>
          <p v-if="createError" class="text-[10px] text-red-600 mb-2">{{ createError }}</p>
          <div class="flex items-center gap-2">
            <button
              type="submit"
              :disabled="isCreating || !newTagName.trim()"
              class="px-2.5 py-1 text-[11px] font-medium bg-violet-600 text-white rounded-md hover:bg-violet-700 disabled:opacity-50 transition-colors"
            >{{ isCreating ? 'Creating…' : 'Create' }}</button>
            <button
              type="button"
              class="px-2.5 py-1 text-[11px]"
              style="color: var(--text-3);"
              @click="showNewRuleForm = false"
            >Cancel</button>
          </div>
        </form>

        <!-- Rule list -->
        <div v-if="filteredRules.length === 0 && !tagStore.isLoading" class="px-4 py-10 text-center">
          <p class="text-[12px]" style="color: var(--text-3);">No tag rules yet</p>
          <p class="text-[11px] mt-1" style="color: var(--text-3); opacity: 0.6;">Create one from an S1 tag or click New Rule</p>
        </div>
        <div
          v-for="rule in filteredRules"
          :key="rule.id"
          style="border-bottom: 1px solid var(--border-light);"
        >
          <button
            class="w-full flex items-center gap-2.5 px-3 py-2.5 text-left transition-colors"
            :class="ruleId === rule.id
              ? 'border-l-2 border-violet-500'
              : 'border-l-2 border-transparent'"
            :style="ruleId === rule.id ? 'background: var(--surface-hover);' : ''"
            @click="openRule(rule.id)"
          >
            <div class="flex items-center justify-center w-6 h-6 rounded-md shrink-0" style="background: var(--accent-muted);">
              <svg class="w-3.5 h-3.5" style="color: var(--accent-text);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75">
                <path stroke-linecap="round" stroke-linejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
              </svg>
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-1.5">
                <span class="text-[12px] font-medium truncate" style="color: var(--heading);">{{ rule.tag_name }}</span>
                <span
                  class="shrink-0 text-[9px] font-medium px-1.5 py-0.5 rounded-full"
                  :style="applyStatusStyle(rule.apply_status)"
                >{{ applyStatusLabel(rule.apply_status) }}</span>
              </div>
              <div class="flex items-center gap-2 mt-0.5 text-[10px]" style="color: var(--text-3);">
                <span>{{ rule.patterns.length }} pattern{{ rule.patterns.length !== 1 ? 's' : '' }}</span>
                <span v-if="rule.last_applied_count > 0">{{ rule.last_applied_count }} agents</span>
              </div>
            </div>
            <svg class="w-3.5 h-3.5 shrink-0" style="color: var(--text-3);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>

        <!-- Orphan rules section (rules without matching S1 tag) -->
        <div v-if="orphanRules.length > 0 && sidebarTab === 'rules'" class="mt-2 pt-1" style="border-top: 1px solid var(--border);">
          <p class="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-widest" style="color: var(--text-3); opacity: 0.6;">No matching S1 tag</p>
        </div>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════════════════════════════
         MAIN CONTENT AREA
         ═══════════════════════════════════════════════════════════════════════ -->

    <!-- ── No rule selected: welcome/overview ──────────────────────────────── -->
    <div
      v-if="!ruleId"
      class="flex-1 flex flex-col items-center justify-center text-center px-8"
    >
      <div class="w-14 h-14 rounded-2xl flex items-center justify-center mb-4" style="background: var(--accent-muted);">
        <svg class="w-7 h-7" style="color: var(--accent-text);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
        </svg>
      </div>
      <h2 class="text-[17px] font-semibold mb-1.5" style="color: var(--heading);">Tag Management</h2>
      <p class="text-[13px] max-w-md mb-6 leading-relaxed" style="color: var(--text-3);">
        Select an S1 tag from the sidebar to create or edit a rule, or click a rule to manage its patterns. Tag rules match installed applications to automatically assign S1 tags to agents.
      </p>
      <div class="flex items-center gap-6 text-center">
        <div class="flex flex-col items-center gap-1.5">
          <div class="w-10 h-10 rounded-xl flex items-center justify-center" style="background: var(--info-bg);">
            <span class="text-[15px] font-bold" style="color: var(--info-text);">{{ s1Tags.length }}</span>
          </div>
          <span class="text-[11px]" style="color: var(--text-3);">S1 Tags</span>
        </div>
        <div class="flex flex-col items-center gap-1.5">
          <div class="w-10 h-10 rounded-xl flex items-center justify-center" style="background: var(--accent-bg);">
            <span class="text-[15px] font-bold" style="color: var(--accent-text);">{{ tagStore.rules.length }}</span>
          </div>
          <span class="text-[11px]" style="color: var(--text-3);">Rules</span>
        </div>
        <div class="flex flex-col items-center gap-1.5">
          <div class="w-10 h-10 rounded-xl flex items-center justify-center" style="background: var(--status-ok-bg);">
            <span class="text-[15px] font-bold" style="color: var(--status-ok-text);">{{ tagStore.rules.filter(r => r.apply_status === 'done').length }}</span>
          </div>
          <span class="text-[11px]" style="color: var(--text-3);">Applied</span>
        </div>
      </div>
    </div>

    <!-- ── Active rule: three-panel editor ─────────────────────────────────── -->
    <template v-else>

      <!-- ── Active rule header ──────────────────────────────────────────── -->
      <div class="flex-1 flex flex-col overflow-hidden">
        <div class="shrink-0 flex items-center gap-3 px-6 py-3" style="background: var(--surface); border-bottom: 1px solid var(--border);">
          <!-- Back arrow -->
          <button
            class="shrink-0 w-7 h-7 flex items-center justify-center rounded-lg transition-colors"
            style="color: var(--text-3);"
            title="Back to tags"
            @click="router.push({ name: 'tags' })"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div class="flex items-center justify-center w-7 h-7 rounded-lg shrink-0" style="background: var(--accent-bg);">
            <svg class="w-[15px] h-[15px]" style="color: var(--accent-text);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75">
              <path stroke-linecap="round" stroke-linejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
            </svg>
          </div>
          <div class="min-w-0 flex-1">
            <div v-if="isEditingName" class="flex items-center gap-2">
              <input
                v-model="editingName"
                class="text-[15px] font-semibold rounded px-2 py-0.5 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                style="color: var(--heading); border: 1px solid rgb(165 180 252);"
                @blur="commitName"
                @keydown.enter="commitName"
                @keydown.esc="isEditingName = false"
                autofocus
              />
            </div>
            <div v-else class="flex items-center gap-2 cursor-pointer group" @click="startEditName">
              <p class="text-[15px] font-semibold leading-none truncate" style="color: var(--heading);">
                {{ tagStore.activeRule?.tag_name }}
              </p>
              <svg class="w-3.5 h-3.5 shrink-0" style="color: var(--text-3);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
              </svg>
            </div>
            <p v-if="tagStore.activeRule?.description" class="text-[11px] leading-none mt-1 truncate" style="color: var(--text-3);">
              {{ tagStore.activeRule.description }}
            </p>
          </div>
          <!-- Apply status badge -->
          <span
            v-if="tagStore.activeRule"
            class="shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium"
            :style="applyStatusStyle(tagStore.activeRule.apply_status)"
          >
            <span
              v-if="tagStore.activeRule.apply_status === 'running'"
              class="inline-block w-2 h-2 rounded-full bg-amber-500 animate-pulse"
            />
            {{ applyStatusLabel(tagStore.activeRule.apply_status) }}
            <span v-if="tagStore.activeRule.apply_status === 'done' && tagStore.activeRule.last_applied_count > 0">
              ({{ tagStore.activeRule.last_applied_count }})
            </span>
          </span>
          <span v-if="hasPatterns" class="text-[12px]" style="color: var(--text-3);">
            {{ patterns.length }} pattern{{ patterns.length !== 1 ? 's' : '' }}
          </span>
          <button
            class="shrink-0 hover:text-red-500 transition-colors"
            style="color: var(--text-3);"
            title="Delete this tag rule"
            @click="deleteActiveRule"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>

        <!-- ── Three-panel row ─────────────────────────────────────────────── -->
        <div class="flex flex-1 overflow-hidden">

          <!-- ── Left: Taxonomy catalog ────────────────────────────────────── -->
          <div class="w-[220px] shrink-0 flex flex-col overflow-hidden" style="border-right: 1px solid var(--border); background: var(--surface-alt);">
            <div class="px-3 py-2.5 shrink-0" style="border-bottom: 1px solid var(--border);">
              <p class="text-[10px] font-semibold uppercase tracking-widest mb-1.5" style="color: var(--text-3);">Catalog</p>
              <input
                v-model="catalogSearch"
                type="text"
                placeholder="Search catalog…"
                class="w-full text-[12px] px-2.5 py-1.5 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-400 placeholder:text-[var(--text-3)]"
                style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
              />
            </div>
            <div class="flex-1 overflow-y-auto">

              <!-- Search results mode -->
              <template v-if="hasCatalogSearch">
                <div v-if="isCatalogSearching" class="px-4 py-4 text-center">
                  <p class="text-[11px] italic" style="color: var(--text-3);">Searching…</p>
                </div>
                <div v-else-if="catalogSearchResults.length === 0" class="px-4 py-4 text-center">
                  <p class="text-[11px]" style="color: var(--text-3);">No entries found</p>
                </div>
                <div v-else>
                  <p class="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-widest" style="color: var(--text-3); opacity: 0.6;">
                    {{ catalogSearchResults.length }} results
                  </p>
                  <div
                    v-for="entry in catalogSearchResults"
                    :key="entry.id"
                    draggable="true"
                    class="group flex items-center justify-between px-4 py-1.5 hover-surface cursor-grab transition-colors"
                    @dragstart="onDragStart($event, entry)"
                  >
                    <div class="flex-1 min-w-0">
                      <span class="text-[11px] truncate block" style="color: var(--text-2);">{{ entry.name }}</span>
                      <span class="text-[10px]" style="color: var(--text-3); opacity: 0.6;">{{ entry.category }}</span>
                    </div>
                    <button
                      class="ml-2 shrink-0 opacity-0 group-hover:opacity-100 w-5 h-5 flex items-center justify-center rounded hover:bg-violet-600 hover:text-white transition-all text-[14px] leading-none" style="background: var(--accent-muted); color: var(--accent-text);"
                      title="Add as pattern"
                      @click.stop="addEntryAsPattern(entry)"
                    >+</button>
                  </div>
                </div>
              </template>

              <!-- Category tree mode (no search) -->
              <template v-else>
                <div v-for="cat in filteredCategories" :key="cat.key">
                  <button
                    class="w-full flex items-center justify-between px-3 py-2 transition-colors text-left"
                    @click="toggleCategory(cat.key)"
                  >
                    <div class="flex items-center gap-2 min-w-0">
                      <svg
                        class="w-3 h-3 shrink-0 transition-transform"
                        :class="expandedCategory === cat.key ? 'rotate-90' : ''"
                        style="color: var(--text-3);"
                        fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"
                      >
                        <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
                      </svg>
                      <span class="text-[12px] font-medium truncate" style="color: var(--text-2);">{{ cat.display }}</span>
                    </div>
                    <span class="ml-1 shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded-full" style="background: var(--badge-bg); color: var(--badge-text);">
                      {{ cat.entry_count }}
                    </span>
                  </button>
                  <div v-if="expandedCategory === cat.key" style="background: var(--surface); border-bottom: 1px solid var(--border-light);">
                    <div
                      v-if="taxStore.isLoading && !taxStore.entriesByCategory[cat.key]"
                      class="px-6 py-2 text-[11px] italic"
                      style="color: var(--text-3);"
                    >Loading…</div>
                    <div
                      v-for="entry in taxStore.entriesByCategory[cat.key] ?? []"
                      :key="entry.id"
                      draggable="true"
                      class="group flex items-center justify-between px-4 pl-8 py-1.5 hover-surface cursor-grab transition-colors"
                      @dragstart="onDragStart($event, entry)"
                    >
                      <span class="text-[11px] truncate flex-1 min-w-0" style="color: var(--text-2);">{{ entry.name }}</span>
                      <button
                        class="ml-2 shrink-0 opacity-0 group-hover:opacity-100 w-5 h-5 flex items-center justify-center rounded hover:bg-violet-600 hover:text-white transition-all text-[14px] leading-none" style="background: var(--accent-muted); color: var(--accent-text);"
                        title="Add as pattern"
                        @click.stop="addEntryAsPattern(entry)"
                      >+</button>
                    </div>
                  </div>
                </div>
              </template>
            </div>
          </div>

          <!-- ── Center: Patterns ──────────────────────────────────────────── -->
          <div class="flex-1 flex flex-col overflow-hidden min-w-0" style="border-right: 1px solid var(--border);">
            <div class="px-5 py-2.5 shrink-0" style="border-bottom: 1px solid var(--border);">
              <p class="text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">
                Tag Rule Patterns
              </p>
            </div>
            <div
              class="flex-1 overflow-y-auto p-5 transition-colors"
              :style="isDragOver ? 'background: var(--surface-hover);' : ''"
              @dragover="onDragOver"
              @dragleave="onDragLeave"
              @drop="onDrop"
            >
              <div
                v-if="!hasPatterns"
                class="flex flex-col items-center justify-center h-full border-2 border-dashed rounded-xl gap-3 transition-colors"
                :style="isDragOver
                  ? 'background: var(--surface-hover); border-color: var(--accent-text); color: var(--accent-text);'
                  : 'border-color: var(--border); color: var(--text-3);'"
              >
                <svg class="w-10 h-10 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
                </svg>
                <p class="text-[13px] font-medium">Drag entries from the catalog</p>
                <p class="text-[12px] opacity-70">or click the + button on any entry</p>
              </div>
              <div v-else class="space-y-2">
                <div
                  v-for="p in patterns"
                  :key="p.id"
                  class="rounded-lg transition-all cursor-pointer group"
                  :class="selectedPatternId === p.id ? 'shadow-sm' : 'hover:shadow-sm'"
                  :style="selectedPatternId === p.id
                    ? 'background: var(--accent-bg); border: 1px solid var(--accent-text);'
                    : 'background: var(--surface); border: 1px solid var(--border);'"
                  @click="selectPattern(p)"
                >
                  <div class="flex items-center gap-3 px-4 py-3">
                    <svg
                      class="w-4 h-4 shrink-0 cursor-grab"
                      style="color: var(--text-3);"
                      fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"
                    >
                      <path stroke-linecap="round" stroke-linejoin="round" d="M4 8h16M4 16h16" />
                    </svg>
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-2 min-w-0">
                        <span class="text-[13px] font-medium truncate" style="color: var(--heading);">{{ p.display_name }}</span>
                        <span
                          class="shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded-full"
                          :style="sourceStyle(p.source)"
                        >{{ p.source }}</span>
                      </div>
                      <code class="text-[11px] font-mono" style="color: var(--text-3);">{{ p.pattern }}</code>
                    </div>
                    <button
                      class="shrink-0 w-6 h-6 flex items-center justify-center rounded hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
                      style="color: var(--text-3);"
                      title="Remove pattern"
                      @click.stop="removePattern(p.id)"
                    >
                      <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </div>
                <div
                  v-if="isDragOver"
                  class="flex items-center justify-center h-12 rounded-lg border-2 border-dashed text-[12px] font-medium"
                  style="border-color: var(--accent-text); color: var(--accent-text);"
                >
                  Drop to add pattern
                </div>
              </div>
            </div>
            <!-- Action bar -->
            <div class="shrink-0 flex items-center gap-2 px-5 py-3" style="background: var(--surface); border-top: 1px solid var(--border);">
              <button
                class="inline-flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-medium rounded-lg disabled:opacity-50 transition-colors"
                style="border: 1px solid var(--border); color: var(--text-2);"
                :disabled="tagStore.isPreviewLoading || patterns.length === 0"
                @click="runPreview"
              >
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
                {{ tagStore.isPreviewLoading ? 'Previewing…' : 'Preview' }}
              </button>
              <button
                class="inline-flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-medium bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50 transition-colors"
                :disabled="tagStore.isApplying || patterns.length === 0 || tagStore.activeRule?.apply_status === 'running'"
                @click="runApply"
              >
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                </svg>
                {{ tagStore.isApplying ? 'Applying…' : 'Apply to S1' }}
              </button>
              <p v-if="patterns.length === 0" class="text-[11px]" style="color: var(--text-3);">
                Add patterns before previewing or applying
              </p>
              <p v-if="tagStore.error" class="text-[11px] text-red-500">{{ tagStore.error }}</p>
            </div>
          </div>

          <!-- ── Right: Preview ────────────────────────────────────────────── -->
          <div class="w-[280px] shrink-0 flex flex-col overflow-hidden" style="background: var(--surface-alt);">
            <div class="px-4 py-2.5 shrink-0" style="border-bottom: 1px solid var(--border);">
              <p class="text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">
                {{ rightPanelMode === 'agents' ? 'Agent Preview' : 'Pattern Preview' }}
              </p>
            </div>

            <!-- ── Pattern preview mode ──────────────────────────────────── -->
            <template v-if="rightPanelMode === 'pattern'">
              <div
                v-if="!selectedPatternId"
                class="flex flex-col items-center justify-center flex-1 gap-3 p-4 text-center"
                style="color: var(--text-3);"
              >
                <svg class="w-8 h-8 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
                <p class="text-[12px]">Click a pattern to see which apps match</p>
              </div>
              <div
                v-else-if="isLoadingPreview"
                class="flex flex-col items-center justify-center flex-1 gap-2"
                style="color: var(--text-3);"
              >
                <svg class="w-5 h-5 animate-spin" style="color: var(--accent-text);" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <p class="text-[12px]">Searching…</p>
              </div>
              <div v-else class="flex flex-col overflow-hidden flex-1">
                <div v-if="selectedPattern" class="px-4 py-3 shrink-0" style="border-bottom: 1px solid var(--border); background: var(--surface);">
                  <code class="text-[12px] font-mono block truncate" style="color: var(--accent-text);">{{ selectedPattern.pattern }}</code>
                  <div class="mt-1.5 flex items-center gap-2">
                    <span
                      class="text-[11px] font-semibold px-2 py-0.5 rounded-full"
                      :style="patternPreview && patternPreview.total_apps > 0 ? 'background: var(--status-ok-bg); color: var(--status-ok-text);' : 'background: var(--status-neutral-bg); color: var(--status-neutral-text);'"
                    >{{ patternPreview?.total_apps ?? 0 }} apps</span>
                    <span
                      class="text-[11px] font-semibold px-2 py-0.5 rounded-full"
                      :style="patternPreview && patternPreview.total_agents > 0 ? 'background: var(--info-bg); color: var(--info-text);' : 'background: var(--status-neutral-bg); color: var(--status-neutral-text);'"
                    >{{ patternPreview?.total_agents ?? 0 }} agents</span>
                  </div>
                </div>
                <div
                  v-if="!patternPreview || patternPreview.app_matches.length === 0"
                  class="flex flex-col items-center justify-center flex-1 gap-2 p-4 text-center"
                  style="color: var(--text-3);"
                >
                  <p class="text-[12px]">
                    {{ patternPreview ? 'No apps matched this pattern.' : 'Run a sync to see live matches.' }}
                  </p>
                </div>
                <div v-else class="flex-1 overflow-y-auto">
                  <div
                    v-for="app in patternPreview.app_matches"
                    :key="app.normalized_name"
                    class="px-4 py-2.5 transition-colors"
                    style="border-bottom: 1px solid var(--border-light);"
                  >
                    <p class="text-[12px] font-medium truncate" style="color: var(--heading);">{{ app.display_name }}</p>
                    <div class="flex items-center justify-between mt-0.5">
                      <p class="text-[11px] truncate" style="color: var(--text-3);">{{ app.publisher || 'Unknown publisher' }}</p>
                      <span class="shrink-0 text-[10px] font-medium" style="color: var(--text-3);">{{ app.agent_count }} agents</span>
                    </div>
                  </div>
                  <div v-if="patternPreview.group_counts.length > 0" class="px-4 py-3" style="border-top: 1px solid var(--border); background: var(--surface-inset);">
                    <p class="text-[10px] font-semibold uppercase tracking-widest mb-2" style="color: var(--text-3);">By Group</p>
                    <div class="space-y-1">
                      <div
                        v-for="gc in patternPreview.group_counts"
                        :key="gc.group_name"
                        class="flex items-center justify-between"
                      >
                        <span class="text-[11px] truncate" style="color: var(--text-2);">{{ gc.group_name }}</span>
                        <span class="shrink-0 text-[10px] font-medium" style="color: var(--text-3);">{{ gc.agent_count }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>

            <!-- ── Agent preview mode ────────────────────────────────────── -->
            <template v-else>
              <div
                v-if="!tagStore.previewResult && !tagStore.isPreviewLoading"
                class="flex-1 flex flex-col items-center justify-center text-center px-4"
              >
                <svg class="w-8 h-8 mb-3" style="color: var(--text-3); opacity: 0.5;" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p class="text-[12px]" style="color: var(--text-3);">Click Preview to see matching agents</p>
              </div>
              <div v-else-if="tagStore.isPreviewLoading" class="flex-1 flex flex-col items-center justify-center gap-2" style="color: var(--text-3);">
                <svg class="w-5 h-5 animate-spin" style="color: var(--accent-text);" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <p class="text-[12px]">Previewing agents…</p>
              </div>
              <div v-else-if="tagStore.previewResult" class="flex-1 flex flex-col min-h-0 overflow-hidden">
                <!-- Header count -->
                <div class="px-4 py-2.5 shrink-0 flex items-center justify-between" style="border-bottom: 1px solid var(--border); background: var(--surface);">
                  <span class="text-[11px] font-semibold px-2 py-0.5 rounded-full" style="background: var(--accent-bg); color: var(--accent-text);">
                    {{ tagStore.previewResult.matched_count.toLocaleString() }} agents
                  </span>
                  <button
                    class="text-[11px] transition-colors"
                    style="color: var(--text-3);"
                    @click="rightPanelMode = 'pattern'"
                  >Back to patterns</button>
                </div>
                <div
                  v-if="tagStore.previewResult.preview_capped"
                  class="shrink-0 px-4 py-2"
                  style="background: var(--warn-bg); border-bottom: 1px solid var(--warn-border);"
                >
                  <p class="text-[11px]" style="color: var(--warn-text);">
                    Showing first 500 of {{ tagStore.previewResult.matched_count.toLocaleString() }}
                  </p>
                </div>
                <!-- Agent list -->
                <div class="flex-1 overflow-y-auto">
                  <div
                    v-for="agent in tagStore.previewResult.agents"
                    :key="agent.s1_agent_id"
                    class="px-4 py-3 transition-colors"
                    style="border-bottom: 1px solid var(--border-light);"
                  >
                    <div class="flex items-center justify-between">
                      <p class="text-[12px] font-medium truncate" style="color: var(--heading);">{{ agent.hostname }}</p>
                      <span class="shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded" style="background: var(--badge-bg); color: var(--badge-text);">{{ agent.os_type }}</span>
                    </div>
                    <p class="text-[11px] truncate mt-0.5" style="color: var(--text-3);">
                      {{ agent.site_name }} / {{ agent.group_name }}
                    </p>
                    <!-- Matched patterns -->
                    <div v-if="agent.matched_patterns.length > 0" class="flex flex-wrap gap-1 mt-1.5">
                      <span
                        v-for="mp in agent.matched_patterns"
                        :key="mp"
                        class="text-[10px] px-1.5 py-0.5 rounded font-mono"
                        style="background: var(--accent-bg); color: var(--accent-text);"
                      >{{ mp }}</span>
                    </div>
                    <!-- Existing S1 tags -->
                    <div v-if="agent.existing_tags.length > 0" class="flex flex-wrap gap-1 mt-1.5">
                      <span class="text-[10px] mr-0.5" style="color: var(--text-3); opacity: 0.6;">Tags:</span>
                      <span
                        v-for="tag in agent.existing_tags"
                        :key="tag"
                        class="text-[10px] px-1.5 py-0.5 rounded font-medium"
                        style="background: var(--info-bg); color: var(--info-text);"
                      >{{ tag }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
