<!--
  Settings view — organized into tabs for classification, sync, security,
  authentication, backup storage, and branding.
  All configurable values are persisted to MongoDB via /api/v1/config/.
-->
<script setup lang="ts">
import { onMounted, ref, computed, onUnmounted } from 'vue'
import * as configApi from '@/api/config'
// ── Tab navigation ───────────────────────────────────────────────────────────
const tabs = [
  { id: 'classification', label: 'Classification', icon: 'M9 12l2 2 4-4' },
  { id: 'sync', label: 'Sync & Proposals', icon: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15' },
  { id: 'security', label: 'Security', icon: 'M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z' },
  { id: 'auth', label: 'Authentication', icon: 'M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z' },
  { id: 'backup', label: 'Backup Storage', icon: 'M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12' },
  { id: 'branding', label: 'Branding', icon: 'M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01' },
] as const
type TabId = typeof tabs[number]['id']
const activeTab = ref<TabId>('classification')

// ── Config state ─────────────────────────────────────────────────────────────
const classificationThreshold  = ref(0.70)
const partialThreshold         = ref(0.40)
const ambiguityGap             = ref(0.15)
const universalAppThreshold    = ref(0.60)
const suggestionScoreThreshold = ref(0.50)
const refreshIntervalMinutes   = ref(60)
const proposalCoverageMin      = ref(0.60)
const proposalOutsideMax       = ref(0.25)
const proposalLiftMin          = ref(2.0)
const proposalTopK             = ref(100)

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

// ── OIDC SSO config ──────────────────────────────────────────────────────────
const oidcEnabledCfg      = ref(false)
const oidcDiscoveryUrl    = ref('')
const oidcClientId        = ref('')
const oidcClientSecret    = ref('')
const oidcRedirectUri     = ref('')
const oidcDefaultRole     = ref('viewer')

// ── SAML SSO config ──────────────────────────────────────────────────────────
const samlEnabledCfg      = ref(false)
const samlIdpMetadataUrl  = ref('')
const samlSpEntityId      = ref('')
const samlSpAcsUrl        = ref('')
const samlDefaultRole     = ref('viewer')

// ── Backup storage config ────────────────────────────────────────────────────
const backupStorageType  = ref('local')
const backupLocalPath    = ref('./backups')
const backupLocalPathWritable = ref(false)
const backupS3Endpoint   = ref('')
const backupS3Bucket     = ref('sentora-backups')
const backupS3AccessKey  = ref('')
const backupS3SecretKey  = ref('')
const backupS3Region     = ref('us-east-1')

const appOrigin = computed(() => typeof globalThis.window !== 'undefined' ? globalThis.window.location.origin : 'https://sentora.example.com')

const brandAppName      = ref('Sentora')
const brandTagline      = ref('EDR Asset Classification')
const brandPrimaryColor = ref('#6366f1')
const brandLogoUrl      = ref('')
const brandFaviconUrl   = ref('')

const isLoadingConfig = ref(false)
const configLoadError = ref<string | null>(null)

// ── Save state (per tab) ─────────────────────────────────────────────────────
const isSaving   = ref(false)
const saveStatus = ref<'idle' | 'saved' | 'error'>('idle')
const saveError  = ref<string | null>(null)
let _saveTimer: ReturnType<typeof setTimeout> | null = null

function clearSaveTimer() {
  if (_saveTimer) { clearTimeout(_saveTimer); _saveTimer = null }
}

function showSaved() {
  saveStatus.value = 'saved'
  clearSaveTimer()
  _saveTimer = setTimeout(() => { saveStatus.value = 'idle' }, 3000)
}

onUnmounted(clearSaveTimer)

function thresholdLabel(v: number): string {
  if (v >= 0.8) return 'Strict'
  if (v >= 0.6) return 'Balanced'
  return 'Lenient'
}

// ── Load ─────────────────────────────────────────────────────────────────────
async function loadConfig() {
  isLoadingConfig.value = true
  configLoadError.value = null
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
    oidcEnabledCfg.value    = cfg.oidc_enabled         ?? oidcEnabledCfg.value
    oidcDiscoveryUrl.value  = cfg.oidc_discovery_url   ?? oidcDiscoveryUrl.value
    oidcClientId.value      = cfg.oidc_client_id       ?? oidcClientId.value
    oidcClientSecret.value  = cfg.oidc_client_secret   ?? oidcClientSecret.value
    oidcRedirectUri.value   = cfg.oidc_redirect_uri    ?? oidcRedirectUri.value
    oidcDefaultRole.value   = cfg.oidc_default_role    ?? oidcDefaultRole.value
    samlEnabledCfg.value    = cfg.saml_enabled         ?? samlEnabledCfg.value
    samlIdpMetadataUrl.value = cfg.saml_idp_metadata_url ?? samlIdpMetadataUrl.value
    samlSpEntityId.value    = cfg.saml_sp_entity_id    ?? samlSpEntityId.value
    samlSpAcsUrl.value      = cfg.saml_sp_acs_url      ?? samlSpAcsUrl.value
    samlDefaultRole.value   = cfg.saml_default_role    ?? samlDefaultRole.value
    backupStorageType.value = cfg.backup_storage_type  ?? backupStorageType.value
    backupLocalPath.value   = cfg.backup_local_path    ?? backupLocalPath.value
    backupLocalPathWritable.value = cfg.backup_local_path_writable ?? false
    backupS3Endpoint.value  = cfg.backup_s3_endpoint   ?? backupS3Endpoint.value
    backupS3Bucket.value    = cfg.backup_s3_bucket     ?? backupS3Bucket.value
    backupS3AccessKey.value = cfg.backup_s3_access_key ?? backupS3AccessKey.value
    backupS3SecretKey.value = cfg.backup_s3_secret_key ?? backupS3SecretKey.value
    backupS3Region.value    = cfg.backup_s3_region     ?? backupS3Region.value
    brandAppName.value      = cfg.brand_app_name      ?? brandAppName.value
    brandTagline.value      = cfg.brand_tagline       ?? brandTagline.value
    brandPrimaryColor.value = cfg.brand_primary_color  ?? brandPrimaryColor.value
    brandLogoUrl.value      = cfg.brand_logo_url       ?? brandLogoUrl.value
    brandFaviconUrl.value   = cfg.brand_favicon_url    ?? brandFaviconUrl.value
  } catch (err) {
    configLoadError.value = err instanceof Error ? err.message : 'Failed to load configuration'
  } finally {
    isLoadingConfig.value = false
  }
}

// ── Save helpers ─────────────────────────────────────────────────────────────
async function saveClassification() {
  isSaving.value = true; saveStatus.value = 'idle'; saveError.value = null
  try {
    await configApi.updateConfig({
      classification_threshold: classificationThreshold.value,
      partial_threshold: partialThreshold.value,
      ambiguity_gap: ambiguityGap.value,
      universal_app_threshold: universalAppThreshold.value,
      suggestion_score_threshold: suggestionScoreThreshold.value,
    })
    showSaved()
  } catch (e) { saveStatus.value = 'error'; saveError.value = e instanceof Error ? e.message : 'Save failed' }
  finally { isSaving.value = false }
}

async function saveSyncAndProposals() {
  isSaving.value = true; saveStatus.value = 'idle'; saveError.value = null
  try {
    await configApi.updateConfig({
      refresh_interval_minutes: refreshIntervalMinutes.value,
      proposal_coverage_min: proposalCoverageMin.value,
      proposal_outside_max: proposalOutsideMax.value,
      proposal_lift_min: proposalLiftMin.value,
      proposal_top_k: proposalTopK.value,
    })
    showSaved()
  } catch (e) { saveStatus.value = 'error'; saveError.value = e instanceof Error ? e.message : 'Save failed' }
  finally { isSaving.value = false }
}

async function saveSecurity() {
  isSaving.value = true; saveStatus.value = 'idle'; saveError.value = null
  try {
    await configApi.updateConfig({
      session_max_lifetime_days: sessionMaxLifetimeDays.value,
      session_inactivity_timeout_days: sessionInactivityTimeoutDays.value,
      account_lockout_threshold: accountLockoutThreshold.value,
      account_lockout_duration_minutes: accountLockoutDurationMinutes.value,
      password_min_length: passwordMinLength.value,
      password_require_uppercase: passwordRequireUppercase.value,
      password_require_lowercase: passwordRequireLowercase.value,
      password_require_digit: passwordRequireDigit.value,
      password_require_special: passwordRequireSpecial.value,
      password_history_count: passwordHistoryCount.value,
      password_max_age_days: passwordMaxAgeDays.value,
      password_check_breached: passwordCheckBreached.value,
    })
    showSaved()
  } catch (e) { saveStatus.value = 'error'; saveError.value = e instanceof Error ? e.message : 'Save failed' }
  finally { isSaving.value = false }
}

async function saveBranding() {
  isSaving.value = true; saveStatus.value = 'idle'; saveError.value = null
  try {
    await configApi.updateConfig({
      brand_app_name: brandAppName.value,
      brand_tagline: brandTagline.value,
      brand_primary_color: brandPrimaryColor.value,
      brand_logo_url: brandLogoUrl.value,
      brand_favicon_url: brandFaviconUrl.value,
    })
    showSaved()
  } catch (e) { saveStatus.value = 'error'; saveError.value = e instanceof Error ? e.message : 'Save failed' }
  finally { isSaving.value = false }
}

async function saveBackup() {
  isSaving.value = true; saveStatus.value = 'idle'; saveError.value = null
  try {
    const cfg = await configApi.updateConfig({
      backup_storage_type: backupStorageType.value,
      backup_local_path: backupLocalPath.value,
      backup_s3_endpoint: backupS3Endpoint.value,
      backup_s3_bucket: backupS3Bucket.value,
      backup_s3_access_key: backupS3AccessKey.value,
      backup_s3_secret_key: backupS3SecretKey.value,
      backup_s3_region: backupS3Region.value,
    })
    backupLocalPathWritable.value = cfg.backup_local_path_writable ?? false
    showSaved()
  } catch (e) {
    saveStatus.value = 'error'
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    saveError.value = msg || (e instanceof Error ? e.message : 'Save failed')
  }
  finally { isSaving.value = false }
}

async function saveAuth() {
  isSaving.value = true; saveStatus.value = 'idle'; saveError.value = null
  try {
    await configApi.updateConfig({
      oidc_enabled: oidcEnabledCfg.value,
      oidc_discovery_url: oidcDiscoveryUrl.value,
      oidc_client_id: oidcClientId.value,
      oidc_client_secret: oidcClientSecret.value,
      oidc_redirect_uri: oidcRedirectUri.value,
      oidc_default_role: oidcDefaultRole.value,
      saml_enabled: samlEnabledCfg.value,
      saml_idp_metadata_url: samlIdpMetadataUrl.value,
      saml_sp_entity_id: samlSpEntityId.value,
      saml_sp_acs_url: samlSpAcsUrl.value,
      saml_default_role: samlDefaultRole.value,
    })
    showSaved()
  } catch (e) { saveStatus.value = 'error'; saveError.value = e instanceof Error ? e.message : 'Save failed' }
  finally { isSaving.value = false }
}

const activeSave = computed(() => {
  switch (activeTab.value) {
    case 'classification': return saveClassification
    case 'sync': return saveSyncAndProposals
    case 'security': return saveSecurity
    case 'backup': return saveBackup
    case 'auth': return saveAuth
    case 'branding': return saveBranding
    default: return null
  }
})

onMounted(loadConfig)
</script>

<template>
  <div class="max-w-[780px] mx-auto px-4 py-6 space-y-4">

    <!-- ── Tab bar ──────────────────────────────────────────────────────────── -->
    <nav class="flex gap-1 rounded-xl p-1" style="background: var(--surface); border: 1px solid var(--border);" role="tablist" aria-label="Settings sections">
      <button
        v-for="tab in tabs" :key="tab.id"
        role="tab"
        :aria-selected="activeTab === tab.id"
        :aria-controls="`panel-${tab.id}`"
        class="flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12px] font-medium transition-all whitespace-nowrap"
        :style="activeTab === tab.id
          ? 'background: var(--brand-primary); color: white;'
          : 'color: var(--text-2); background: transparent;'"
        @click="activeTab = tab.id"
      >
        <svg class="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" :d="tab.icon" />
        </svg>
        {{ tab.label }}
      </button>
    </nav>

    <!-- ── Loading / Error ──────────────────────────────────────────────────── -->
    <div v-if="isLoadingConfig" class="text-center py-12">
      <div class="skeleton h-4 w-48 mx-auto mb-3"></div>
      <div class="skeleton h-3 w-32 mx-auto"></div>
    </div>
    <div v-else-if="configLoadError" class="rounded-xl px-5 py-4" style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);">
      <p class="text-[13px] font-medium">{{ configLoadError }}</p>
    </div>

    <template v-else>

      <!-- ═══ CLASSIFICATION TAB ═══════════════════════════════════════════════ -->
      <div v-show="activeTab === 'classification'" :id="`panel-classification`" role="tabpanel" class="space-y-4">
        <div class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
          <div class="px-5 py-4" style="border-bottom: 1px solid var(--border-light);">
            <h2 class="text-[14px] font-semibold" style="color: var(--heading);">Classification Thresholds</h2>
            <p class="text-[12px] mt-0.5" style="color: var(--text-3);">Tune the confidence cutoffs used when assigning verdicts</p>
          </div>
          <div class="px-5 py-5 space-y-5">
            <div v-for="slider in [
              { id: 'matched', model: classificationThreshold, min: 0.5, max: 0.95, step: 0.05, color: 'indigo', label: 'Matched threshold', help: 'Agents scoring \u2265 this value are classified as correct.' },
              { id: 'partial', model: partialThreshold, min: 0.1, max: 0.65, step: 0.05, color: 'orange', label: 'Partial threshold', help: 'Scores between this and matched threshold yield ambiguous.' },
              { id: 'ambiguity', model: ambiguityGap, min: 0.05, max: 0.40, step: 0.05, color: 'amber', label: 'Ambiguity gap', help: 'Minimum score gap between top two groups before result is ambiguous.' },
              { id: 'universal', model: universalAppThreshold, min: 0.3, max: 0.9, step: 0.05, color: 'teal', label: 'Universal app threshold', help: 'Fraction of agents an app must appear in to be universal (excluded from scoring).' },
              { id: 'suggestion', model: suggestionScoreThreshold, min: 0.1, max: 0.9, step: 0.05, color: 'violet', label: 'Suggestion score threshold', help: 'Minimum TF-IDF score for a suggestion to surface in the editor.' },
            ]" :key="slider.id">
              <div class="flex items-center justify-between mb-1.5">
                <label :for="`threshold-${slider.id}`" class="text-[12px] font-medium" style="color: var(--text-2);">{{ slider.label }}</label>
                <div class="flex items-center gap-2">
                  <span class="text-[12px] font-semibold" style="color: var(--brand-primary);">{{ slider.model.toFixed(2) }}</span>
                  <span v-if="slider.id === 'matched'" class="text-[10px] font-medium px-1.5 py-0.5 rounded-full" style="background: var(--info-bg); color: var(--info-text);">
                    {{ thresholdLabel(slider.model) }}
                  </span>
                </div>
              </div>
              <input
                :id="`threshold-${slider.id}`"
                v-model.number="slider.model"
                type="range" :min="slider.min" :max="slider.max" :step="slider.step"
                :aria-label="slider.label" :aria-valuenow="slider.model"
                class="w-full accent-indigo-600"
              />
              <p class="text-[11px] mt-1" style="color: var(--text-3);">{{ slider.help }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══ SYNC & PROPOSALS TAB ═════════════════════════════════════════════ -->
      <div v-show="activeTab === 'sync'" :id="`panel-sync`" role="tabpanel" class="space-y-4">
        <!-- Refresh schedule -->
        <div class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
          <div class="px-5 py-4" style="border-bottom: 1px solid var(--border-light);">
            <h2 class="text-[14px] font-semibold" style="color: var(--heading);">Refresh Schedule</h2>
            <p class="text-[12px] mt-0.5" style="color: var(--text-3);">How often the scheduler triggers an incremental refresh (0 = disabled)</p>
          </div>
          <div class="px-5 py-4 flex items-center gap-4">
            <div class="flex items-center gap-2">
              <input v-model.number="refreshIntervalMinutes" type="number" min="0" max="1440" step="15"
                aria-label="Refresh interval in minutes"
                class="w-24 px-3 py-2 text-[13px] rounded-lg outline-none"
                style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
              <span class="text-[12px]" style="color: var(--text-3);">minutes</span>
            </div>
            <span v-if="refreshIntervalMinutes === 0" class="text-[12px] font-medium" style="color: var(--warn-text);">Disabled</span>
          </div>
        </div>
        <!-- Proposal thresholds -->
        <div class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
          <div class="px-5 py-4" style="border-bottom: 1px solid var(--border-light);">
            <h2 class="text-[14px] font-semibold" style="color: var(--heading);">Fingerprint Proposal Thresholds</h2>
            <p class="text-[12px] mt-0.5" style="color: var(--text-3);">Controls what the Lift-based auto-proposer considers a good marker</p>
          </div>
          <div class="px-5 py-5 space-y-5">
            <div v-for="slider in [
              { id: 'cov-min', model: proposalCoverageMin, min: 0.1, max: 1.0, step: 0.05, label: 'Min in-group coverage', fmt: (v: number) => `${Math.round(v * 100)}%`, help: 'Minimum fraction of group agents that must have the app.' },
              { id: 'out-max', model: proposalOutsideMax, min: 0.0, max: 0.5, step: 0.05, label: 'Max outside coverage', fmt: (v: number) => `${Math.round(v * 100)}%`, help: 'Maximum fraction of non-group agents that may also have the app.' },
              { id: 'lift-min', model: proposalLiftMin, min: 1, max: 20, step: 0.5, label: 'Min lift', fmt: (v: number) => `${v}\u00d7`, help: 'How many times more likely the app appears in this group vs. the fleet.' },
              { id: 'top-k', model: proposalTopK, min: 1, max: 200, step: 5, label: 'Max markers per group', fmt: (v: number) => `${v}`, help: 'Maximum number of markers proposed per group.' },
            ]" :key="slider.id">
              <div class="flex items-center justify-between mb-1.5">
                <label :for="`proposal-${slider.id}`" class="text-[12px] font-medium" style="color: var(--text-2);">{{ slider.label }}</label>
                <span class="text-[12px] font-semibold" style="color: var(--brand-primary);">{{ slider.fmt(slider.model) }}</span>
              </div>
              <input :id="`proposal-${slider.id}`" v-model.number="slider.model" type="range" :min="slider.min" :max="slider.max" :step="slider.step" :aria-label="slider.label" class="w-full accent-indigo-600" />
              <p class="text-[11px] mt-1" style="color: var(--text-3);">{{ slider.help }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══ SECURITY TAB ═════════════════════════════════════════════════════ -->
      <div v-show="activeTab === 'security'" :id="`panel-security`" role="tabpanel" class="space-y-4">
        <div class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
          <div class="px-5 py-4" style="border-bottom: 1px solid var(--border-light);">
            <h2 class="text-[14px] font-semibold" style="color: var(--heading);">Security Settings</h2>
            <p class="text-[12px] mt-0.5" style="color: var(--text-3);">Session management, account lockout, and password policy</p>
          </div>
          <div class="px-5 py-5 space-y-5">
            <!-- Sessions -->
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
                  <label for="lockout-threshold" class="text-[12px] font-medium" style="color: var(--text-2);">Failed attempts</label>
                  <input id="lockout-threshold" v-model.number="accountLockoutThreshold" type="number" min="1" max="100" class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
                </div>
                <div>
                  <label for="lockout-duration" class="text-[12px] font-medium" style="color: var(--text-2);">Lockout duration (min)</label>
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
                  <label for="pw-history" class="text-[12px] font-medium" style="color: var(--text-2);">History count</label>
                  <input id="pw-history" v-model.number="passwordHistoryCount" type="number" min="0" max="24" class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
                  <p class="text-[11px] mt-1" style="color: var(--text-3);">0 = no history check</p>
                </div>
              </div>
              <div>
                <label for="pw-max-age" class="text-[12px] font-medium" style="color: var(--text-2);">Max password age (days)</label>
                <input id="pw-max-age" v-model.number="passwordMaxAgeDays" type="number" min="0" max="365" class="w-32 mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
                <span class="text-[11px] ml-2" style="color: var(--text-3);">0 = no expiry (NIST-compliant)</span>
              </div>
              <div class="space-y-2 pt-1">
                <label v-for="opt in [
                  { model: passwordRequireUppercase, label: 'Require uppercase letter' },
                  { model: passwordRequireLowercase, label: 'Require lowercase letter' },
                  { model: passwordRequireDigit, label: 'Require digit' },
                  { model: passwordRequireSpecial, label: 'Require special character', note: '(NIST recommends against)' },
                  { model: passwordCheckBreached, label: 'Check passwords against HaveIBeenPwned', note: '(k-Anonymity \u2014 password never leaves server)' },
                ]" :key="opt.label" class="flex items-center gap-2 text-[12px]" style="color: var(--text-2);">
                  <input v-model="opt.model" type="checkbox" class="accent-indigo-600" />
                  {{ opt.label }}
                  <span v-if="opt.note" class="text-[11px] italic" style="color: var(--text-3);">{{ opt.note }}</span>
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══ AUTHENTICATION TAB ═══════════════════════════════════════════════ -->
      <div v-show="activeTab === 'auth'" :id="`panel-auth`" role="tabpanel" class="space-y-4">
        <!-- Local auth (always on) -->
        <div class="rounded-xl px-5 py-4 flex items-center gap-3" style="background: var(--success-bg); border: 1px solid var(--success-border);">
          <div class="w-8 h-8 rounded-full flex items-center justify-center shrink-0" style="background: var(--success-text); color: white;">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" /></svg>
          </div>
          <div>
            <p class="text-[13px] font-semibold" style="color: var(--text-1);">Local Authentication</p>
            <p class="text-[11px]" style="color: var(--text-3);">Username + password + TOTP 2FA — always active</p>
          </div>
        </div>

        <!-- OIDC config -->
        <div class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
          <div class="px-5 py-4 flex items-center justify-between" style="border-bottom: 1px solid var(--border-light);">
            <div>
              <h2 class="text-[14px] font-semibold" style="color: var(--heading);">OpenID Connect (OIDC)</h2>
              <p class="text-[12px] mt-0.5" style="color: var(--text-3);">Azure AD, Okta, Google Workspace, Keycloak, etc.</p>
            </div>
            <label class="flex items-center gap-2 text-[12px] font-medium cursor-pointer" style="color: var(--text-2);">
              <input v-model="oidcEnabledCfg" type="checkbox" class="accent-indigo-600" />
              Enable
            </label>
          </div>
          <div v-if="oidcEnabledCfg" class="px-5 py-5 space-y-3">
            <div>
              <label for="oidc-discovery" class="text-[12px] font-medium" style="color: var(--text-2);">Discovery URL</label>
              <input id="oidc-discovery" v-model="oidcDiscoveryUrl" type="url" placeholder="https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration" class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label for="oidc-client-id" class="text-[12px] font-medium" style="color: var(--text-2);">Client ID</label>
                <input id="oidc-client-id" v-model="oidcClientId" type="text" class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
              </div>
              <div>
                <label for="oidc-client-secret" class="text-[12px] font-medium" style="color: var(--text-2);">Client Secret</label>
                <input id="oidc-client-secret" v-model="oidcClientSecret" type="password" autocomplete="off" class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
                <p class="text-[11px] mt-1" style="color: var(--text-3);">Encrypted at rest in the database</p>
              </div>
            </div>
            <div>
              <label for="oidc-redirect" class="text-[12px] font-medium" style="color: var(--text-2);">Redirect URI (callback)</label>
              <input id="oidc-redirect" v-model="oidcRedirectUri" type="url" :placeholder="`${appOrigin}/auth/oidc/callback`" class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
            </div>
            <div>
              <label for="oidc-role" class="text-[12px] font-medium" style="color: var(--text-2);">Default role for new OIDC users</label>
              <select id="oidc-role" v-model="oidcDefaultRole" class="mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);">
                <option value="viewer">Viewer</option>
                <option value="analyst">Analyst</option>
                <option value="admin">Admin</option>
              </select>
            </div>
          </div>
        </div>

        <!-- SAML config -->
        <div class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
          <div class="px-5 py-4 flex items-center justify-between" style="border-bottom: 1px solid var(--border-light);">
            <div>
              <h2 class="text-[14px] font-semibold" style="color: var(--heading);">SAML 2.0</h2>
              <p class="text-[12px] mt-0.5" style="color: var(--text-3);">ADFS, PingFederate, Shibboleth, etc.</p>
            </div>
            <label class="flex items-center gap-2 text-[12px] font-medium cursor-pointer" style="color: var(--text-2);">
              <input v-model="samlEnabledCfg" type="checkbox" class="accent-indigo-600" />
              Enable
            </label>
          </div>
          <div v-if="samlEnabledCfg" class="px-5 py-5 space-y-3">
            <div>
              <label for="saml-metadata" class="text-[12px] font-medium" style="color: var(--text-2);">IdP Metadata URL</label>
              <input id="saml-metadata" v-model="samlIdpMetadataUrl" type="url" placeholder="https://idp.example.com/metadata.xml" class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label for="saml-entity-id" class="text-[12px] font-medium" style="color: var(--text-2);">SP Entity ID</label>
                <input id="saml-entity-id" v-model="samlSpEntityId" type="text" :placeholder="`${appOrigin}/api/v1/auth/saml/metadata`" class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
              </div>
              <div>
                <label for="saml-acs" class="text-[12px] font-medium" style="color: var(--text-2);">SP ACS URL (callback)</label>
                <input id="saml-acs" v-model="samlSpAcsUrl" type="url" :placeholder="`${appOrigin}/api/v1/auth/saml/callback`" class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
              </div>
            </div>
            <div>
              <label for="saml-role" class="text-[12px] font-medium" style="color: var(--text-2);">Default role for new SAML users</label>
              <select id="saml-role" v-model="samlDefaultRole" class="mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);">
                <option value="viewer">Viewer</option>
                <option value="analyst">Analyst</option>
                <option value="admin">Admin</option>
              </select>
            </div>
          </div>
        </div>

        <p class="text-[11px]" style="color: var(--text-3);">
          Settings are stored per-tenant. In multi-tenant deployments, each tenant can configure its own identity provider.
          Environment variable settings (if any) are used as fallback when no database config exists.
        </p>
      </div>

      <!-- ═══ BACKUP STORAGE TAB ══════════════════════════════════════════════ -->
      <div v-show="activeTab === 'backup'" :id="`panel-backup`" role="tabpanel" class="space-y-4">
        <div class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
          <div class="px-5 py-4" style="border-bottom: 1px solid var(--border-light);">
            <h2 class="text-[14px] font-semibold" style="color: var(--heading);">Backup Storage Backend</h2>
            <p class="text-[12px] mt-0.5" style="color: var(--text-3);">Choose where database backups are stored. S3-compatible storage works with MinIO, AWS S3, GCS, and others.</p>
          </div>
          <div class="px-5 py-5 space-y-4">
            <!-- Storage type selector -->
            <div>
              <label class="text-[12px] font-medium" style="color: var(--text-2);">Storage type</label>
              <div class="flex gap-3 mt-2">
                <label class="flex items-center gap-2 px-4 py-2.5 rounded-lg cursor-pointer transition-all text-[13px] font-medium"
                  :style="backupStorageType === 'local' ? 'background: var(--info-bg); color: var(--info-text); border: 2px solid var(--brand-primary);' : 'background: var(--surface-alt); color: var(--text-2); border: 2px solid var(--border);'">
                  <input v-model="backupStorageType" type="radio" value="local" class="accent-indigo-600" />
                  Local Filesystem
                </label>
                <label class="flex items-center gap-2 px-4 py-2.5 rounded-lg cursor-pointer transition-all text-[13px] font-medium"
                  :style="backupStorageType === 's3' ? 'background: var(--info-bg); color: var(--info-text); border: 2px solid var(--brand-primary);' : 'background: var(--surface-alt); color: var(--text-2); border: 2px solid var(--border);'">
                  <input v-model="backupStorageType" type="radio" value="s3" class="accent-indigo-600" />
                  S3-Compatible (MinIO / AWS / GCS)
                </label>
              </div>
            </div>

            <!-- S3 config (shown when s3 selected) -->
            <template v-if="backupStorageType === 's3'">
              <div>
                <label for="s3-endpoint" class="text-[12px] font-medium" style="color: var(--text-2);">S3 Endpoint URL</label>
                <input id="s3-endpoint" v-model="backupS3Endpoint" type="url" placeholder="http://minio:9000 or https://s3.amazonaws.com" class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
                <p class="text-[11px] mt-1" style="color: var(--text-3);">For MinIO: use the internal Docker network URL. For AWS: leave empty to use the default regional endpoint.</p>
              </div>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label for="s3-bucket" class="text-[12px] font-medium" style="color: var(--text-2);">Bucket Name</label>
                  <input id="s3-bucket" v-model="backupS3Bucket" type="text" class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
                </div>
                <div>
                  <label for="s3-region" class="text-[12px] font-medium" style="color: var(--text-2);">Region</label>
                  <input id="s3-region" v-model="backupS3Region" type="text" placeholder="us-east-1" class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
                </div>
              </div>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label for="s3-access-key" class="text-[12px] font-medium" style="color: var(--text-2);">Access Key ID</label>
                  <input id="s3-access-key" v-model="backupS3AccessKey" type="text" autocomplete="off" class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
                </div>
                <div>
                  <label for="s3-secret-key" class="text-[12px] font-medium" style="color: var(--text-2);">Secret Access Key</label>
                  <input id="s3-secret-key" v-model="backupS3SecretKey" type="password" autocomplete="off" class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
                  <p class="text-[11px] mt-1" style="color: var(--text-3);">Encrypted at rest in the database</p>
                </div>
              </div>
            </template>

            <!-- Local config (shown when local selected) -->
            <div v-else class="space-y-3">
              <div>
                <label for="backup-local-path" class="text-[12px] font-medium" style="color: var(--text-2);">Backup directory path</label>
                <div class="flex gap-2 mt-1">
                  <input
                    id="backup-local-path"
                    v-model="backupLocalPath"
                    type="text"
                    placeholder="./backups or /var/sentora/backups"
                    class="flex-1 px-3 py-2 text-[13px] rounded-lg"
                    style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);"
                  />
                  <span
                    class="inline-flex items-center gap-1 px-3 py-2 rounded-lg text-[12px] font-medium whitespace-nowrap"
                    :style="backupLocalPathWritable
                      ? 'background: var(--success-bg); color: var(--success-text);'
                      : 'background: var(--error-bg); color: var(--error-text);'"
                  >
                    <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path v-if="backupLocalPathWritable" stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                      <path v-else stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                    {{ backupLocalPathWritable ? 'Writable' : 'Not writable' }}
                  </span>
                </div>
                <p class="text-[11px] mt-1" style="color: var(--text-3);">
                  Absolute or relative path on the server. Writability is verified when you save.
                  The directory will be created automatically if it does not exist.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══ BRANDING TAB ═════════════════════════════════════════════════════ -->
      <div v-show="activeTab === 'branding'" :id="`panel-branding`" role="tabpanel" class="space-y-4">
        <div class="rounded-xl overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
          <div class="px-5 py-4" style="border-bottom: 1px solid var(--border-light);">
            <h2 class="text-[14px] font-semibold" style="color: var(--heading);">White-Label Branding</h2>
            <p class="text-[12px] mt-0.5" style="color: var(--text-3);">Customize the application name, colors, and logo for your organization</p>
          </div>
          <div class="px-5 py-5 space-y-4">
            <div>
              <label for="brand-name" class="text-[12px] font-medium" style="color: var(--text-2);">Application name</label>
              <input id="brand-name" v-model="brandAppName" type="text" maxlength="50" class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
            </div>
            <div>
              <label for="brand-tagline" class="text-[12px] font-medium" style="color: var(--text-2);">Tagline</label>
              <input id="brand-tagline" v-model="brandTagline" type="text" maxlength="100" class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
            </div>
            <div>
              <label for="brand-color" class="text-[12px] font-medium" style="color: var(--text-2);">Primary color</label>
              <div class="flex items-center gap-3 mt-1">
                <input id="brand-color" v-model="brandPrimaryColor" type="color" class="w-10 h-10 rounded-lg cursor-pointer border-0" />
                <input v-model="brandPrimaryColor" type="text" maxlength="7" class="w-28 px-3 py-2 text-[13px] rounded-lg font-mono" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
                <div class="w-24 h-10 rounded-lg" :style="{ background: brandPrimaryColor }"></div>
              </div>
            </div>
            <div>
              <label for="brand-logo" class="text-[12px] font-medium" style="color: var(--text-2);">Logo URL</label>
              <input id="brand-logo" v-model="brandLogoUrl" type="url" placeholder="https://..." class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
              <p class="text-[11px] mt-1" style="color: var(--text-3);">Replaces the sidebar brand text. Recommended: SVG or PNG, max 200px wide.</p>
            </div>
            <div>
              <label for="brand-favicon" class="text-[12px] font-medium" style="color: var(--text-2);">Favicon URL</label>
              <input id="brand-favicon" v-model="brandFaviconUrl" type="url" placeholder="https://..." class="w-full mt-1 px-3 py-2 text-[13px] rounded-lg" style="border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text-1);" />
            </div>
          </div>
        </div>
      </div>

    </template>

    <!-- ── Save footer (visible on saveable tabs) ───────────────────────────── -->
    <div v-if="activeSave && !isLoadingConfig" class="flex items-center justify-between rounded-xl px-5 py-3" style="background: var(--surface); border: 1px solid var(--border);">
      <p class="text-[11px]" style="color: var(--text-3);">Changes take effect on the next run or page load.</p>
      <div class="flex items-center gap-3">
        <span v-if="saveStatus === 'saved'" class="text-[12px] font-medium flex items-center gap-1" style="color: var(--success-text);">
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" /></svg>
          Saved
        </span>
        <span v-else-if="saveStatus === 'error'" class="text-[12px] font-medium" style="color: var(--error-text);">{{ saveError || 'Save failed' }}</span>
        <button
          class="px-4 py-1.5 rounded-lg text-white text-[13px] font-medium transition-colors disabled:opacity-50"
          style="background: var(--brand-primary);"
          :disabled="isSaving"
          aria-label="Save settings"
          @click="activeSave?.()"
        >
          {{ isSaving ? 'Saving\u2026' : 'Save Settings' }}
        </button>
      </div>
    </div>

  </div>
</template>
