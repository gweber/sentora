<!--
  Audit Chain view — forensic hash-chain status, verification, and epoch export.
-->
<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import {
  getChainStatus,
  verifyChain,
  listEpochs,
  exportEpoch,
  type ChainStatusResponse,
  type VerifyChainResponse,
  type EpochSummary,
} from '@/api/auditChain'
import { formatDateTime, formatRelativeTime } from '@/utils/formatters'

// ── State ─────────────────────────────────────────────────────────────────────

const chainStatus = ref<ChainStatusResponse | null>(null)
const epochs = ref<EpochSummary[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

// Verification
const verifying = ref(false)
const verifyResult = ref<VerifyChainResponse | null>(null)
const verifyError = ref<string | null>(null)

// Export
const exporting = ref<number | null>(null)

// ── Data loading ──────────────────────────────────────────────────────────────

async function loadStatus() {
  loading.value = true
  error.value = null
  try {
    const [status, epochList] = await Promise.all([getChainStatus(), listEpochs()])
    chainStatus.value = status
    epochs.value = epochList.epochs
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to load chain status'
  } finally {
    loading.value = false
  }
}

async function runVerification() {
  verifying.value = true
  verifyError.value = null
  verifyResult.value = null
  try {
    verifyResult.value = await verifyChain({ epoch: null })
  } catch (e: unknown) {
    verifyError.value = e instanceof Error ? e.message : 'Verification failed'
  } finally {
    verifying.value = false
  }
}

async function downloadEpoch(epochNum: number) {
  exporting.value = epochNum
  try {
    const blob = await exportEpoch(epochNum)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `audit_epoch_${epochNum}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Export failed'
  } finally {
    exporting.value = null
  }
}

onMounted(loadStatus)

// ── Computed ──────────────────────────────────────────────────────────────────

const statusColor = computed(() => {
  if (!chainStatus.value) return 'var(--text-3)'
  if (chainStatus.value.chain_valid === true) return 'var(--status-ok-text)'
  if (chainStatus.value.chain_valid === false) return 'var(--status-error-text)'
  return 'var(--status-warn-text)'
})

const statusLabel = computed(() => {
  if (!chainStatus.value) return 'Unknown'
  if (chainStatus.value.chain_valid === true) return 'Valid'
  if (chainStatus.value.chain_valid === false) return 'Broken'
  return 'Not Verified'
})

const verifyStatusColor = computed(() => {
  if (!verifyResult.value) return ''
  if (verifyResult.value.status === 'valid') return 'var(--status-ok-text)'
  return 'var(--status-error-text)'
})

function truncHash(hash: string, len = 12): string {
  return hash ? hash.substring(0, len) + '...' : '-'
}
</script>

<template>
  <div class="p-6 space-y-5 max-w-[1100px]">

    <!-- Header -->
    <div>
      <h2 class="text-[15px] font-semibold" style="color: var(--heading);">Audit Chain</h2>
      <p class="text-[12px] mt-0.5" style="color: var(--text-3);">
        Forensic hash-chain verification, epoch management, and cold-storage export
      </p>
    </div>

    <!-- Error -->
    <div
      v-if="error"
      class="rounded-lg px-4 py-3 text-[13px]"
      style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);"
    >
      {{ error }}
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading && !chainStatus" class="space-y-4">
      <div class="skeleton h-32 rounded-xl" />
      <div class="skeleton h-48 rounded-xl" />
    </div>

    <!-- Chain Status Card -->
    <div
      v-if="chainStatus"
      class="rounded-xl p-5"
      style="background: var(--surface); border: 1px solid var(--border);"
    >
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-3">
          <div
            class="w-3 h-3 rounded-full shrink-0"
            :style="{ background: statusColor }"
          />
          <div>
            <span class="text-[13px] font-semibold" style="color: var(--heading);">
              Audit Chain:
            </span>
            <span class="text-[13px] font-semibold ml-1" :style="{ color: statusColor }">
              {{ statusLabel }}
            </span>
          </div>
        </div>
        <button
          class="flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-medium rounded-md transition-colors"
          style="background: var(--brand-primary); color: white;"
          :disabled="verifying"
          @click="runVerification"
        >
          <svg
            v-if="verifying"
            class="w-3.5 h-3.5 animate-spin"
            fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          {{ verifying ? 'Verifying...' : 'Verify Now' }}
        </button>
      </div>

      <!-- Stats grid -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div>
          <div class="text-[11px] uppercase tracking-wider font-medium" style="color: var(--text-3);">Total Entries</div>
          <div class="text-[15px] font-semibold tabular-nums mt-0.5" style="color: var(--heading);">
            {{ chainStatus.total_entries.toLocaleString() }}
          </div>
        </div>
        <div>
          <div class="text-[11px] uppercase tracking-wider font-medium" style="color: var(--text-3);">Current Epoch</div>
          <div class="text-[15px] font-semibold tabular-nums mt-0.5" style="color: var(--heading);">
            {{ chainStatus.current_epoch }}
          </div>
        </div>
        <div>
          <div class="text-[11px] uppercase tracking-wider font-medium" style="color: var(--text-3);">Genesis Hash</div>
          <div
            class="text-[12px] font-mono mt-0.5"
            style="color: var(--text-2);"
            :title="chainStatus.genesis_hash"
          >
            {{ truncHash(chainStatus.genesis_hash) }}
          </div>
        </div>
        <div>
          <div class="text-[11px] uppercase tracking-wider font-medium" style="color: var(--text-3);">Latest Hash</div>
          <div
            class="text-[12px] font-mono mt-0.5"
            style="color: var(--text-2);"
            :title="chainStatus.latest_hash"
          >
            {{ truncHash(chainStatus.latest_hash) }}
          </div>
        </div>
      </div>

      <!-- Last verified -->
      <div v-if="chainStatus.last_verified_at" class="mt-3 text-[11px]" style="color: var(--text-3);">
        Last verified: {{ formatRelativeTime(chainStatus.last_verified_at) }}
        <span class="ml-1">({{ formatDateTime(chainStatus.last_verified_at) }})</span>
      </div>
    </div>

    <!-- Verification Result -->
    <div
      v-if="verifyResult"
      class="rounded-xl p-4"
      :style="{
        background: verifyResult.status === 'valid' ? 'var(--success-bg)' : 'var(--error-bg)',
        border: `1px solid ${verifyResult.status === 'valid' ? 'var(--success-border)' : 'var(--error-border)'}`,
      }"
    >
      <div class="flex items-center gap-2 mb-2">
        <span class="text-[13px] font-semibold" :style="{ color: verifyStatusColor }">
          {{ verifyResult.status === 'valid' ? 'Chain Valid' : 'Chain Integrity Violation Detected' }}
        </span>
      </div>
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[12px]" style="color: var(--text-2);">
        <div>
          <span style="color: var(--text-3);">Entries verified:</span>
          {{ verifyResult.verified_entries.toLocaleString() }}
        </div>
        <div>
          <span style="color: var(--text-3);">Epochs verified:</span>
          {{ verifyResult.epochs_verified }}
        </div>
        <div>
          <span style="color: var(--text-3);">Time:</span>
          {{ verifyResult.verification_time_ms }}ms
        </div>
        <div v-if="verifyResult.broken_at_sequence !== null">
          <span style="color: var(--status-error-text);">Broken at seq:</span>
          {{ verifyResult.broken_at_sequence }}
          <span v-if="verifyResult.broken_reason" class="text-[11px]">
            ({{ verifyResult.broken_reason }})
          </span>
        </div>
      </div>
    </div>

    <!-- Verification Error -->
    <div
      v-if="verifyError"
      class="rounded-lg px-4 py-3 text-[13px]"
      style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);"
    >
      {{ verifyError }}
    </div>

    <!-- Epoch List -->
    <div
      v-if="epochs.length > 0"
      class="rounded-xl overflow-hidden"
      style="background: var(--surface); border: 1px solid var(--border);"
    >
      <div class="px-5 py-3 flex items-center justify-between" style="border-bottom: 1px solid var(--border);">
        <h3 class="text-[13px] font-semibold" style="color: var(--heading);">
          Completed Epochs
        </h3>
        <span class="text-[11px] tabular-nums" style="color: var(--text-3);">
          {{ epochs.length }} epoch{{ epochs.length !== 1 ? 's' : '' }}
        </span>
      </div>

      <table class="w-full border-collapse">
        <thead>
          <tr style="background: var(--surface-inset); border-bottom: 1px solid var(--border);">
            <th scope="col" class="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Epoch</th>
            <th scope="col" class="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Sequences</th>
            <th scope="col" class="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Period</th>
            <th scope="col" class="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Entries</th>
            <th scope="col" class="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Final Hash</th>
            <th scope="col" class="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-widest" style="color: var(--text-3);">Status</th>
            <th scope="col" class="px-4 py-2.5 w-20" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="ep in epochs"
            :key="ep.epoch"
            style="border-bottom: 1px solid var(--border-light);"
          >
            <td class="px-4 py-3 text-[13px] font-semibold tabular-nums" style="color: var(--heading);">
              {{ ep.epoch }}
            </td>
            <td class="px-4 py-3 text-[12px] font-mono tabular-nums" style="color: var(--text-2);">
              {{ ep.first_sequence }}-{{ ep.last_sequence }}
            </td>
            <td class="px-4 py-3 text-[12px]" style="color: var(--text-3);">
              <span :title="formatDateTime(ep.first_timestamp)">{{ formatRelativeTime(ep.first_timestamp) }}</span>
              —
              <span :title="formatDateTime(ep.last_timestamp)">{{ formatRelativeTime(ep.last_timestamp) }}</span>
            </td>
            <td class="px-4 py-3 text-[12px] tabular-nums" style="color: var(--text-2);">
              {{ ep.entry_count.toLocaleString() }}
            </td>
            <td class="px-4 py-3 text-[11px] font-mono" style="color: var(--text-3);" :title="ep.epoch_final_hash">
              {{ truncHash(ep.epoch_final_hash, 10) }}
            </td>
            <td class="px-4 py-3">
              <span
                v-if="ep.exported"
                class="text-[11px] font-medium px-2 py-0.5 rounded-full"
                style="background: var(--status-ok-bg); color: var(--status-ok-text);"
              >Exported</span>
              <span
                v-else
                class="text-[11px] font-medium px-2 py-0.5 rounded-full badge-neutral"
              >Ready</span>
            </td>
            <td class="px-4 py-3 text-right">
              <button
                class="text-[11px] font-medium px-2.5 py-1 rounded-md transition-colors"
                style="color: var(--brand-primary); border: 1px solid var(--border); background: var(--surface);"
                :disabled="exporting === ep.epoch"
                @click="downloadEpoch(ep.epoch)"
              >
                {{ exporting === ep.epoch ? '...' : 'Export' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Empty epoch state -->
    <div
      v-else-if="!loading && chainStatus"
      class="rounded-xl p-8 text-center"
      style="background: var(--surface); border: 1px solid var(--border);"
    >
      <p class="text-[13px]" style="color: var(--text-3);">
        No completed epochs yet. Epochs are completed after {{ chainStatus.current_epoch > 0 ? '' : '1,000' }} entries.
      </p>
    </div>

  </div>
</template>
