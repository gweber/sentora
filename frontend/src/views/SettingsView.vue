<!--
  Settings view — classification thresholds, page sizes, universal exclusions.
  All configurable values are persisted to MongoDB via /api/v1/config/.
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import * as configApi from '@/api/config'
import * as taxonomyApi from '@/api/taxonomy'
import type { SoftwareEntry } from '@/types/taxonomy'

// ── Config (classification thresholds) ────────────────────────────────────────
const classificationThreshold  = ref(0.70)
const partialThreshold         = ref(0.40)
const ambiguityGap             = ref(0.15)
const universalAppThreshold    = ref(0.60)
const suggestionScoreThreshold = ref(0.50)

const isLoadingConfig = ref(false)
const configLoadError = ref<string | null>(null)
const isSaving        = ref(false)
const saveStatus      = ref<'idle' | 'saved' | 'error'>('idle')
const saveError       = ref<string | null>(null)

function thresholdLabel(v: number): string {
  if (v >= 0.8) return 'Strict'
  if (v >= 0.6) return 'Balanced'
  return 'Lenient'
}

async function loadConfig() {
  isLoadingConfig.value = true
  try {
    const cfg = await configApi.getConfig()
    classificationThreshold.value  = cfg.classification_threshold  ?? classificationThreshold.value
    partialThreshold.value         = cfg.partial_threshold         ?? partialThreshold.value
    ambiguityGap.value             = cfg.ambiguity_gap             ?? ambiguityGap.value
    universalAppThreshold.value    = cfg.universal_app_threshold   ?? universalAppThreshold.value
    suggestionScoreThreshold.value = cfg.suggestion_score_threshold ?? suggestionScoreThreshold.value
    refreshIntervalMinutes.value   = cfg.refresh_interval_minutes  ?? refreshIntervalMinutes.value
    proposalCoverageMin.value      = cfg.proposal_coverage_min     ?? proposalCoverageMin.value
    proposalOutsideMax.value       = cfg.proposal_outside_max      ?? proposalOutsideMax.value
    proposalLiftMin.value          = cfg.proposal_lift_min         ?? proposalLiftMin.value
    proposalTopK.value             = cfg.proposal_top_k            ?? proposalTopK.value
    sessionMaxLifetimeDays.value        = cfg.session_max_lifetime_days        ?? sessionMaxLifetimeDays.value
    sessionInactivityTimeoutDays.value  = cfg.session_inactivity_timeout_days  ?? sessionInactivityTimeoutDays.value
    accountLockoutThreshold.value       = cfg.account_lockout_threshold        ?? accountLockoutThreshold.value
    accountLockoutDurationMinutes.value = cfg.account_lockout_duration_minutes ?? accountLockoutDurationMinutes.value
    passwordMinLength.value             = cfg.password_min_length              ?? passwordMinLength.value
    passwordRequireUppercase.value      = cfg.password_require_uppercase       ?? passwordRequireUppercase.value
    passwordRequireLowercase.value      = cfg.password_require_lowercase       ?? passwordRequireLowercase.value
    passwordRequireDigit.value          = cfg.password_require_digit           ?? passwordRequireDigit.value
    passwordRequireSpecial.value        = cfg.password_require_special         ?? passwordRequireSpecial.value
    passwordHistoryCount.value          = cfg.password_history_count           ?? passwordHistoryCount.value
    passwordMaxAgeDays.value            = cfg.password_max_age_days            ?? passwordMaxAgeDays.value
    passwordCheckBreached.value         = cfg.password_check_breached          ?? passwordCheckBreached.value
  } catch (err) {
    configLoadError.value = err instanceof Error ? err.message : 'Failed to load configuration'
  } finally {
    isLoadingConfig.value = false
  }
}

async function saveConfig() {
  isSaving.value = true
  saveStatus.value = 'idle'
  saveError.value = null
  try {
    await configApi.updateConfig({
      classification_threshold:   classificationThreshold.value,
      partial_threshold:          partialThreshold.value,
      ambiguity_gap:              ambiguityGap.value,
      universal_app_threshold:    universalAppThreshold.value,
      suggestion_score_threshold: suggestionScoreThreshold.value,
    })
    saveStatus.value = 'saved'
    setTimeout(() => { saveStatus.value = 'idle' }, 3000)
  } catch (e) {
    saveStatus.value = 'error'
    saveError.value = e instanceof Error ? e.message : 'Save failed'
  } finally {
    isSaving.value = false
  }
}

// ── Proposal thresholds ───────────────────────────────────────────────────────
const proposalCoverageMin = ref(0.60)
const proposalOutsideMax  = ref(0.25)
const proposalLiftMin     = ref(2.0)
const proposalTopK        = ref(100)

const isSavingProposal  = ref(false)
const proposalSaveStatus = ref<'idle' | 'saved' | 'error'>('idle')

async function saveProposalThresholds() {
  isSavingProposal.value = true
  proposalSaveStatus.value = 'idle'
  try {
    await configApi.updateConfig({
      proposal_coverage_min: proposalCoverageMin.value,
      proposal_outside_max:  proposalOutsideMax.value,
      proposal_lift_min:     proposalLiftMin.value,
      proposal_top_k:        proposalTopK.value,
    })
    proposalSaveStatus.value = 'saved'
    setTimeout(() => { proposalSaveStatus.value = 'idle' }, 3000)
  } catch {
    proposalSaveStatus.value = 'error'
  } finally {
    isSavingProposal.value = false
  }
}

// ── Refresh schedule ──────────────────────────────────────────────────────────
const refreshIntervalMinutes = ref(60)
const isSavingRefresh  = ref(false)
const refreshStatus    = ref<'idle' | 'saved' | 'error'>('idle')

async function saveRefreshInterval() {
  isSavingRefresh.value = true
  refreshStatus.value = 'idle'
  try {
    await configApi.updateConfig({ refresh_interval_minutes: refreshIntervalMinutes.value })
    refreshStatus.value = 'saved'
    setTimeout(() => { refreshStatus.value = 'idle' }, 3000)
  } catch {
    refreshStatus.value = 'error'
  } finally {
    isSavingRefresh.value = false
  }
}

// ── Security settings ────────────────────────────────────────────────────────
const sessionMaxLifetimeDays        = ref(30)
const sessionInactivityTimeoutDays  = ref(30)
const accountLockoutThreshold       = ref(5)
const accountLockoutDurationMinutes = ref(15)
const passwordMinLength             = ref(12)
const passwordRequireUppercase      = ref(true)
const passwordRequireLowercase      = ref(true)
const passwordRequireDigit          = ref(true)
const passwordRequireSpecial        = ref(false)
const passwordHistoryCount          = ref(5)
const passwordMaxAgeDays            = ref(0)
const passwordCheckBreached         = ref(true)

const isSavingSecurity  = ref(false)
const securitySaveStatus = ref<'idle' | 'saved' | 'error'>('idle')

async function saveSecuritySettings() {
  isSavingSecurity.value = true
  securitySaveStatus.value = 'idle'
  try {
    await configApi.updateConfig({
      session_max_lifetime_days:        sessionMaxLifetimeDays.value,
      session_inactivity_timeout_days:  sessionInactivityTimeoutDays.value,
      account_lockout_threshold:        accountLockoutThreshold.value,
      account_lockout_duration_minutes: accountLockoutDurationMinutes.value,
      password_min_length:              passwordMinLength.value,
      password_require_uppercase:       passwordRequireUppercase.value,
      password_require_lowercase:       passwordRequireLowercase.value,
      password_require_digit:           passwordRequireDigit.value,
      password_require_special:         passwordRequireSpecial.value,
      password_history_count:           passwordHistoryCount.value,
      password_max_age_days:            passwordMaxAgeDays.value,
      password_check_breached:          passwordCheckBreached.value,
    })
    securitySaveStatus.value = 'saved'
    setTimeout(() => { securitySaveStatus.value = 'idle' }, 3000)
  } catch {
    securitySaveStatus.value = 'error'
  } finally {
    isSavingSecurity.value = false
  }
}

// ── Universal exclusions ──────────────────────────────────────────────────────
const universalEntries    = ref<SoftwareEntry[]>([])
const isLoadingUniversal  = ref(false)

async function loadUniversal() {
  isLoadingUniversal.value = true
  try {
    const cats = await taxonomyApi.listCategories()
    const all: SoftwareEntry[] = []
    await Promise.all(
      cats.categories.map(async (cat) => {
        const res = await taxonomyApi.getEntriesByCategory(cat.key)
        all.push(...res.entries.filter((e) => e.is_universal))
      }),
    )
    universalEntries.value = all.sort((a, b) => a.name.localeCompare(b.name))
  } catch {
    /* pre-seed state — ignore */
  } finally {
    isLoadingUniversal.value = false
  }
}

const removeUniversalError = ref<string | null>(null)

async function removeUniversal(entry: SoftwareEntry) {
  removeUniversalError.value = null
  try {
    await taxonomyApi.toggleUniversal(entry.id)
    universalEntries.value = universalEntries.value.filter((e) => e.id !== entry.id)
  } catch (e) {
    removeUniversalError.value = e instanceof Error ? e.message : 'Failed to remove universal entry'
  }
}

onMounted(() => Promise.all([loadConfig(), loadUniversal()]))
</script>

<template>
  <div class="p-6 max-w-[720px] space-y-4">

    <!-- ── Classification Thresholds ─────────────────────────────────────────── -->
    <div class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
      <div class="px-5 py-4" style="border-bottom: 1px solid var(--border-light);">
        <h2 class="text-[14px] font-semibold" style="color: var(--heading);">Classification Thresholds</h2>
        <p class="text-[12px] mt-0.5" style="color: var(--text-3);">Tune the confidence cutoffs used when assigning verdicts</p>
      </div>
      <div class="px-5 py-5 space-y-5">
        <div v-if="configLoadError" class="text-[12px] font-medium text-amber-600 mb-3">{{ configLoadError }}</div>
        <div v-if="isLoadingConfig" class="text-[12px] italic" style="color: var(--text-3);">Loading…</div>

        <template v-else>
          <!-- Matched threshold -->
          <div>
            <div class="flex items-center justify-between mb-1.5">
              <label for="threshold-matched" class="text-[12px] font-medium" style="color: var(--text-2);">Matched threshold</label>
              <div class="flex items-center gap-2">
                <span class="text-[12px] font-semibold text-indigo-600">{{ classificationThreshold.toFixed(2) }}</span>
                <span class="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-indigo-50 text-indigo-600">
                  {{ thresholdLabel(classificationThreshold) }}
                </span>
              </div>
            </div>
            <input id="threshold-matched" v-model.number="classificationThreshold" type="range" min="0.5" max="0.95" step="0.05" aria-label="Matched threshold" :aria-valuenow="classificationThreshold" aria-valuemin="0.5" aria-valuemax="0.95" class="w-full accent-indigo-600" />
            <p class="text-[11px] mt-1" style="color: var(--text-3);">Agents scoring ≥ this value are classified as <strong>correct</strong>.</p>
          </div>

          <!-- Partial threshold -->
          <div>
            <div class="flex items-center justify-between mb-1.5">
              <label for="threshold-partial" class="text-[12px] font-medium" style="color: var(--text-2);">Partial threshold</label>
              <span class="text-[12px] font-semibold text-orange-500">{{ partialThreshold.toFixed(2) }}</span>
            </div>
            <input id="threshold-partial" v-model.number="partialThreshold" type="range" min="0.1" max="0.65" step="0.05" aria-label="Partial threshold" :aria-valuenow="partialThreshold" aria-valuemin="0.1" aria-valuemax="0.65" class="w-full accent-orange-400" />
            <p class="text-[11px] mt-1" style="color: var(--text-3);">Scores between this and matched threshold yield <strong>ambiguous</strong>.</p>
          </div>

          <!-- Ambiguity gap -->
          <div>
            <div class="flex items-center justify-between mb-1.5">
              <label for="threshold-ambiguity" class="text-[12px] font-medium" style="color: var(--text-2);">Ambiguity gap</label>
              <span class="text-[12px] font-semibold text-amber-500">{{ ambiguityGap.toFixed(2) }}</span>
            </div>
            <input id="threshold-ambiguity" v-model.number="ambiguityGap" type="range" min="0.05" max="0.40" step="0.05" aria-label="Ambiguity gap" :aria-valuenow="ambiguityGap" aria-valuemin="0.05" aria-valuemax="0.40" class="w-full accent-amber-400" />
            <p class="text-[11px] mt-1" style="color: var(--text-3);">Minimum score gap between top two groups before result is <strong>ambiguous</strong>.</p>
          </div>

          <!-- Universal app threshold -->
          <div>
            <div class="flex items-center justify-between mb-1.5">
              <label for="threshold-universal" class="text-[12px] font-medium" style="color: var(--text-2);">Universal app threshold</label>
              <span class="text-[12px] font-semibold text-teal-600">{{ universalAppThreshold.toFixed(2) }}</span>
            </div>
            <input id="threshold-universal" v-model.number="universalAppThreshold" type="range" min="0.3" max="0.9" step="0.05" aria-label="Universal app threshold" :aria-valuenow="universalAppThreshold" aria-valuemin="0.3" aria-valuemax="0.9" class="w-full accent-teal-500" />
            <p class="text-[11px] mt-1" style="color: var(--text-3);">
              Fraction of agents an app must appear in to be considered <strong>universal</strong> (and excluded from fingerprint scoring).
            </p>
          </div>

          <!-- Suggestion score threshold -->
          <div>
            <div class="flex items-center justify-between mb-1.5">
              <label for="threshold-suggestion" class="text-[12px] font-medium" style="color: var(--text-2);">Suggestion score threshold</label>
              <span class="text-[12px] font-semibold text-violet-600">{{ suggestionScoreThreshold.toFixed(2) }}</span>
            </div>
            <input id="threshold-suggestion" v-model.number="suggestionScoreThreshold" type="range" min="0.1" max="0.9" step="0.05" aria-label="Suggestion score threshold" :aria-valuenow="suggestionScoreThreshold" aria-valuemin="0.1" aria-valuemax="0.9" class="w-full accent-violet-500" />
            <p class="text-[11px] mt-1" style="color: var(--text-3);">Minimum TF-IDF score for a fingerprint suggestion to surface in the editor.</p>
          </div>
        </template>
      </div>
    </div>

    <!-- ── Save footer ─────────────────────────────────────────────────────────── -->
    <div class="flex items-center justify-between rounded-xl px-5 py-3" style="background: var(--surface); border: 1px solid var(--border);">
      <p class="text-[11px]" style="color: var(--text-3);">Changes take effect on the next classification run or page load.</p>
      <div class="flex items-center gap-3">
        <span v-if="saveStatus === 'saved'" class="text-[12px] font-medium text-emerald-600 flex items-center gap-1">
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          Saved
        </span>
        <span v-else-if="saveStatus === 'error'" class="text-[12px] font-medium text-red-500">{{ saveError || 'Save failed' }}</span>
        <button
          class="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[13px] font-medium transition-colors disabled:opacity-50"
          :disabled="isSaving || isLoadingConfig"
          aria-label="Save classification thresholds"
          @click="saveConfig"
        >
          {{ isSaving ? 'Saving…' : 'Save Settings' }}
        </button>
      </div>
    </div>

    <!-- ── Refresh Schedule ───────────────────────────────────────────────────── -->
    <div class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
      <div class="px-5 py-4" style="border-bottom: 1px solid var(--border-light);">
        <h2 class="text-[14px] font-semibold" style="color: var(--heading);">Refresh Schedule</h2>
        <p class="text-[12px] mt-0.5" style="color: var(--text-3);">How often the scheduler triggers an incremental refresh (0 = disabled)</p>
      </div>
      <div class="px-5 py-4 flex items-center gap-4">
        <div class="flex items-center gap-2">
          <input
            id="refresh-interval"
            v-model.number="refreshIntervalMinutes"
            type="number" min="0" max="1440" step="15"
            aria-label="Refresh interval in minutes"
            class="w-24 px-3 py-2 text-[13px] rounded-lg outline-none transition"
            style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);"
          />
          <span class="text-[12px]" style="color: var(--text-3);">minutes</span>
        </div>
        <span v-if="refreshIntervalMinutes === 0" class="text-[12px] text-amber-500 font-medium">Disabled</span>
        <div class="ml-auto flex items-center gap-3">
          <span v-if="refreshStatus === 'saved'" class="text-[12px] font-medium text-emerald-600 flex items-center gap-1">
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            Saved
          </span>
          <span v-else-if="refreshStatus === 'error'" class="text-[12px] font-medium text-red-500">Save failed</span>
          <button
            class="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[13px] font-medium transition-colors disabled:opacity-50"
            :disabled="isSavingRefresh || isLoadingConfig"
            aria-label="Save refresh schedule"
            @click="saveRefreshInterval"
          >
            {{ isSavingRefresh ? 'Saving…' : 'Save' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── Proposal Thresholds ───────────────────────────────────────────────── -->
    <div class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
      <div class="px-5 py-4" style="border-bottom: 1px solid var(--border-light);">
        <h2 class="text-[14px] font-semibold" style="color: var(--heading);">Fingerprint Proposal Thresholds</h2>
        <p class="text-[12px] mt-0.5" style="color: var(--text-3);">Controls what the Lift-based auto-proposer considers a good marker. Applied on the next "Generate Proposals" run.</p>
      </div>
      <div class="px-5 py-5 space-y-5">

        <!-- Coverage min -->
        <div>
          <div class="flex items-center justify-between mb-1.5">
            <label for="proposal-coverage-min" class="text-[12px] font-medium" style="color: var(--text-2);">Min in-group coverage</label>
            <span class="text-[12px] font-semibold text-indigo-600 w-10 text-right">{{ Math.round(proposalCoverageMin * 100) }}%</span>
          </div>
          <input id="proposal-coverage-min" type="range" v-model.number="proposalCoverageMin" min="0.1" max="1.0" step="0.05" aria-label="Minimum in-group coverage" :aria-valuenow="proposalCoverageMin" aria-valuemin="0.1" aria-valuemax="1.0" class="w-full accent-indigo-600" />
          <p class="text-[11px] mt-1" style="color: var(--text-3);">Minimum fraction of group agents that must have the app. Higher = fewer but more reliable markers.</p>
        </div>

        <!-- Outside max -->
        <div>
          <div class="flex items-center justify-between mb-1.5">
            <label for="proposal-outside-max" class="text-[12px] font-medium" style="color: var(--text-2);">Max outside coverage</label>
            <span class="text-[12px] font-semibold text-indigo-600 w-10 text-right">{{ Math.round(proposalOutsideMax * 100) }}%</span>
          </div>
          <input id="proposal-outside-max" type="range" v-model.number="proposalOutsideMax" min="0.0" max="0.5" step="0.05" aria-label="Maximum outside coverage" :aria-valuenow="proposalOutsideMax" aria-valuemin="0.0" aria-valuemax="0.5" class="w-full accent-indigo-600" />
          <p class="text-[11px] mt-1" style="color: var(--text-3);">Maximum fraction of non-group agents that may also have the app. Lower = more exclusive markers.</p>
        </div>

        <!-- Lift min -->
        <div>
          <div class="flex items-center justify-between mb-1.5">
            <label for="proposal-lift-min" class="text-[12px] font-medium" style="color: var(--text-2);">Min lift</label>
            <span class="text-[12px] font-semibold text-indigo-600 w-10 text-right">{{ proposalLiftMin }}×</span>
          </div>
          <input id="proposal-lift-min" type="range" v-model.number="proposalLiftMin" min="1" max="20" step="0.5" aria-label="Minimum lift score" :aria-valuenow="proposalLiftMin" aria-valuemin="1" aria-valuemax="20" class="w-full accent-indigo-600" />
          <p class="text-[11px] mt-1" style="color: var(--text-3);">Minimum lift score required. Lift = how many times more likely the app appears in this group vs. the fleet.</p>
        </div>

        <!-- Top K -->
        <div>
          <div class="flex items-center justify-between mb-1.5">
            <label for="proposal-top-k" class="text-[12px] font-medium" style="color: var(--text-2);">Max markers per group</label>
            <span class="text-[12px] font-semibold text-indigo-600 w-10 text-right">{{ proposalTopK }}</span>
          </div>
          <input id="proposal-top-k" type="range" v-model.number="proposalTopK" min="1" max="200" step="5" aria-label="Maximum markers per group" :aria-valuenow="proposalTopK" aria-valuemin="1" aria-valuemax="200" class="w-full accent-indigo-600" />
          <p class="text-[11px] mt-1" style="color: var(--text-3);">Maximum number of markers proposed per group (top-K by lift score).</p>
        </div>

        <div class="flex items-center justify-end gap-3 pt-1">
          <span v-if="proposalSaveStatus === 'saved'" class="text-[12px] font-medium text-emerald-600 flex items-center gap-1">
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            Saved
          </span>
          <span v-else-if="proposalSaveStatus === 'error'" class="text-[12px] font-medium text-red-500">Save failed</span>
          <button
            class="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[13px] font-medium transition-colors disabled:opacity-50"
            :disabled="isSavingProposal || isLoadingConfig"
            aria-label="Save proposal thresholds"
            @click="saveProposalThresholds"
          >
            {{ isSavingProposal ? 'Saving…' : 'Save' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── Security Settings ──────────────────────────────────────────────────── -->
    <div class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
      <div class="px-5 py-4" style="border-bottom: 1px solid var(--border-light);">
        <h2 class="text-[14px] font-semibold" style="color: var(--heading);">Security Settings</h2>
        <p class="text-[12px] mt-0.5" style="color: var(--text-3);">Session management, account lockout, and password policy</p>
      </div>
      <div class="px-5 py-5 space-y-5">
        <div v-if="isLoadingConfig" class="text-[12px] italic" style="color: var(--text-3);">Loading…</div>
        <template v-else>

          <!-- Session settings -->
          <div class="space-y-3">
            <h3 class="text-[12px] font-semibold uppercase tracking-wider" style="color: var(--text-3);">Sessions</h3>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label for="session-lifetime" class="text-[12px] font-medium" style="color: var(--text-2);">Max lifetime (days)</label>
                <input id="session-lifetime" v-model.number="sessionMaxLifetimeDays" type="number" min="1" max="365" class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
              </div>
              <div>
                <label for="session-inactivity" class="text-[12px] font-medium" style="color: var(--text-2);">Inactivity timeout (days)</label>
                <input id="session-inactivity" v-model.number="sessionInactivityTimeoutDays" type="number" min="1" max="365" class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
              </div>
            </div>
          </div>

          <!-- Account lockout -->
          <div class="space-y-3">
            <h3 class="text-[12px] font-semibold uppercase tracking-wider" style="color: var(--text-3);">Account Lockout</h3>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label for="lockout-threshold" class="text-[12px] font-medium" style="color: var(--text-2);">Failed attempts before lockout</label>
                <input id="lockout-threshold" v-model.number="accountLockoutThreshold" type="number" min="1" max="100" class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
              </div>
              <div>
                <label for="lockout-duration" class="text-[12px] font-medium" style="color: var(--text-2);">Lockout duration (minutes)</label>
                <input id="lockout-duration" v-model.number="accountLockoutDurationMinutes" type="number" min="1" max="1440" class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
              </div>
            </div>
          </div>

          <!-- Password policy -->
          <div class="space-y-3">
            <h3 class="text-[12px] font-semibold uppercase tracking-wider" style="color: var(--text-3);">Password Policy</h3>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label for="pw-min-length" class="text-[12px] font-medium" style="color: var(--text-2);">Minimum length</label>
                <input id="pw-min-length" v-model.number="passwordMinLength" type="number" min="8" max="128" class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
              </div>
              <div>
                <label for="pw-history" class="text-[12px] font-medium" style="color: var(--text-2);">Password history count</label>
                <input id="pw-history" v-model.number="passwordHistoryCount" type="number" min="0" max="24" class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
                <p class="text-[11px] mt-1" style="color: var(--text-3);">0 = no history check</p>
              </div>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label for="pw-max-age" class="text-[12px] font-medium" style="color: var(--text-2);">Max password age (days)</label>
                <input id="pw-max-age" v-model.number="passwordMaxAgeDays" type="number" min="0" max="365" class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
                <p class="text-[11px] mt-1" style="color: var(--text-3);">0 = no expiry (NIST-compliant)</p>
              </div>
            </div>

            <div class="space-y-2 pt-1">
              <label class="flex items-center gap-2 text-[12px]" style="color: var(--text-2);">
                <input v-model="passwordRequireUppercase" type="checkbox" class="accent-indigo-600" />
                Require uppercase letter
              </label>
              <label class="flex items-center gap-2 text-[12px]" style="color: var(--text-2);">
                <input v-model="passwordRequireLowercase" type="checkbox" class="accent-indigo-600" />
                Require lowercase letter
              </label>
              <label class="flex items-center gap-2 text-[12px]" style="color: var(--text-2);">
                <input v-model="passwordRequireDigit" type="checkbox" class="accent-indigo-600" />
                Require digit
              </label>
              <label class="flex items-center gap-2 text-[12px]" style="color: var(--text-2);">
                <input v-model="passwordRequireSpecial" type="checkbox" class="accent-indigo-600" />
                Require special character
                <span class="text-[11px] italic" style="color: var(--text-3);">(NIST recommends against)</span>
              </label>
              <label class="flex items-center gap-2 text-[12px]" style="color: var(--text-2);">
                <input v-model="passwordCheckBreached" type="checkbox" class="accent-indigo-600" />
                Check passwords against HaveIBeenPwned breach database
                <span class="text-[11px] italic" style="color: var(--text-3);">(k-Anonymity — password never leaves server)</span>
              </label>
            </div>
          </div>

          <div class="flex items-center justify-end gap-3 pt-1">
            <span v-if="securitySaveStatus === 'saved'" class="text-[12px] font-medium text-emerald-600 flex items-center gap-1">
              <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              Saved
            </span>
            <span v-else-if="securitySaveStatus === 'error'" class="text-[12px] font-medium text-red-500">Save failed</span>
            <button
              class="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[13px] font-medium transition-colors disabled:opacity-50"
              :disabled="isSavingSecurity || isLoadingConfig"
              aria-label="Save security settings"
              @click="saveSecuritySettings"
            >
              {{ isSavingSecurity ? 'Saving…' : 'Save Security Settings' }}
            </button>
          </div>
        </template>
      </div>
    </div>

    <!-- ── Universal Exclusions ───────────────────────────────────────────────── -->
    <div class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
      <div class="px-5 py-4" style="border-bottom: 1px solid var(--border-light);">
        <h2 class="text-[14px] font-semibold" style="color: var(--heading);">Universal Exclusions</h2>
        <p class="text-[12px] mt-0.5" style="color: var(--text-3);">
          Software flagged as universal is excluded from fingerprint suggestions.
          <span class="font-medium text-indigo-600">{{ universalEntries.length }}</span> entries excluded.
        </p>
      </div>
      <div class="px-5 py-4">
        <div v-if="removeUniversalError" class="text-[12px] font-medium text-red-500 mb-2">{{ removeUniversalError }}</div>
        <div v-if="isLoadingUniversal" class="text-[12px] italic py-2" style="color: var(--text-3);">Loading…</div>
        <div v-else-if="universalEntries.length === 0" class="text-[12px] italic py-2" style="color: var(--text-3);">
          No universal exclusions. Mark entries in the Taxonomy view to exclude them.
        </div>
        <div v-else class="space-y-1 max-h-60 overflow-y-auto">
          <div
            v-for="entry in universalEntries"
            :key="entry.id"
            class="flex items-center justify-between px-3 py-2 rounded-lg transition-colors group"
            style="background: var(--surface-inset);"
          >
            <div class="min-w-0">
              <span class="text-[13px] font-medium" style="color: var(--text-1);">{{ entry.name }}</span>
              <span class="ml-2 text-[11px]" style="color: var(--text-3);">{{ entry.category_display }}</span>
            </div>
            <button
              class="ml-3 shrink-0 text-[11px] font-medium hover:text-red-500 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-all"
              style="color: var(--text-3);"
              :aria-label="`Remove ${entry.name} from universal exclusions`"
              @click="removeUniversal(entry)"
            >
              Remove
            </button>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>
