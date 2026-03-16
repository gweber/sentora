<!--
  TOTP verification modal — 6 single-digit fields with auto-advance.
  Used for both registration (QR code + verify) and login (verify only).
-->
<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted } from 'vue'

const props = defineProps<{
  /** 'setup' shows QR code + verify; 'login' shows verify only */
  mode: 'setup' | 'login'
  /** QR code SVG string (only for setup mode) */
  qrCodeSvg?: string
  /** Whether the parent is loading */
  loading?: boolean
  /** Error message from parent */
  error?: string | null
}>()

const emit = defineEmits<{
  (e: 'verify', code: string): void
  (e: 'close'): void
}>()

/** Render QR SVG safely via <img> data URI — prevents script execution in malicious SVGs */
const qrCodeDataUri = computed(() => {
  if (!props.qrCodeSvg) return ''
  return 'data:image/svg+xml;base64,' + btoa(props.qrCodeSvg)
})

const digits = ref<string[]>(['', '', '', '', '', ''])
const inputRefs = ref<(HTMLInputElement | null)[]>([])
const localError = ref<string | null>(null)

onMounted(() => {
  nextTick(() => inputRefs.value[0]?.focus())
})

// Clear error when user starts typing again
watch(digits, () => {
  localError.value = null
}, { deep: true })

function setRef(el: any, index: number) {
  inputRefs.value[index] = el as HTMLInputElement | null
}

function handleInput(index: number, event: Event) {
  const target = event.target as HTMLInputElement
  const value = target.value

  // Only allow single digit
  if (!/^\d$/.test(value)) {
    digits.value[index] = ''
    target.value = ''
    return
  }

  digits.value[index] = value

  // Auto-advance to next field
  if (index < 5) {
    nextTick(() => inputRefs.value[index + 1]?.focus())
  }

  // Auto-submit when last digit entered
  if (index === 5 && digits.value.every(d => d !== '')) {
    submit()
  }
}

function handleKeydown(index: number, event: KeyboardEvent) {
  // Backspace: clear current field, move to previous
  if (event.key === 'Backspace') {
    if (digits.value[index] === '' && index > 0) {
      digits.value[index - 1] = ''
      nextTick(() => inputRefs.value[index - 1]?.focus())
    } else {
      digits.value[index] = ''
    }
    event.preventDefault()
  }
  // Left arrow
  if (event.key === 'ArrowLeft' && index > 0) {
    inputRefs.value[index - 1]?.focus()
  }
  // Right arrow
  if (event.key === 'ArrowRight' && index < 5) {
    inputRefs.value[index + 1]?.focus()
  }
}

function handlePaste(event: ClipboardEvent) {
  event.preventDefault()
  const pasted = (event.clipboardData?.getData('text') || '').replace(/\D/g, '').slice(0, 6)
  for (let i = 0; i < 6; i++) {
    digits.value[i] = pasted[i] || ''
  }
  // Focus last filled or first empty
  const nextEmpty = digits.value.findIndex(d => d === '')
  const focusIdx = nextEmpty === -1 ? 5 : nextEmpty
  nextTick(() => {
    inputRefs.value[focusIdx]?.focus()
    if (digits.value.every(d => d !== '')) submit()
  })
}

function submit() {
  const code = digits.value.join('')
  if (code.length !== 6) {
    localError.value = 'Please enter all 6 digits'
    return
  }
  emit('verify', code)
}

function reset() {
  digits.value = ['', '', '', '', '', '']
  nextTick(() => inputRefs.value[0]?.focus())
}

// When parent error changes (failed verification), reset fields
watch(() => props.error, (err) => {
  if (err) {
    localError.value = err
    reset()
  }
})

defineExpose({ reset })
</script>

<template>
  <!-- Backdrop -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4" @click.self="emit('close')">
    <div class="rounded-xl shadow-xl w-full max-w-sm p-6" style="background: var(--surface); border: 1px solid var(--border);" role="dialog" aria-modal="true" :aria-label="mode === 'setup' ? 'Set up two-factor authentication' : 'Enter verification code'">

      <!-- Header -->
      <div class="text-center mb-5">
        <div class="inline-flex items-center justify-center w-10 h-10 rounded-full bg-[var(--brand-primary-light)] mb-3">
          <svg class="w-5 h-5 text-[var(--brand-primary)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        </div>
        <h2 class="text-base font-semibold" style="color: var(--heading);">
          {{ mode === 'setup' ? 'Set up 2FA' : 'Two-factor authentication' }}
        </h2>
        <p class="text-sm mt-1" style="color: var(--text-3);">
          {{ mode === 'setup'
            ? 'Scan the QR code with your authenticator app, then enter the 6-digit code'
            : 'Enter the 6-digit code from your authenticator app'
          }}
        </p>
      </div>

      <!-- QR Code (setup mode only) -->
      <div v-if="mode === 'setup' && qrCodeSvg" class="flex justify-center mb-5">
        <div class="p-3 rounded-lg inline-block" style="background: #ffffff; border: 1px solid var(--border);">
          <img :src="qrCodeDataUri" alt="TOTP QR Code" width="200" height="200" />
        </div>
      </div>

      <!-- Error -->
      <div
        v-if="localError"
        class="mb-4 px-3 py-2 text-sm rounded-lg"
        style="background: var(--error-bg); border: 1px solid var(--error-border); color: var(--error-text);"
        role="alert"
      >
        {{ localError }}
      </div>

      <!-- 6-digit input -->
      <div class="flex justify-center gap-2 mb-5" @paste="handlePaste">
        <input
          v-for="(_, i) in 6"
          :key="i"
          :ref="(el) => setRef(el, i)"
          type="text"
          inputmode="numeric"
          autocomplete="one-time-code"
          maxlength="1"
          :value="digits[i]"
          :disabled="loading"
          class="w-11 h-13 text-center text-lg font-semibold rounded-lg outline-none transition disabled:opacity-50"
          style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-1);"
          :aria-label="`Digit ${i + 1} of 6`"
          @input="handleInput(i, $event)"
          @keydown="handleKeydown(i, $event)"
        />
      </div>

      <!-- Actions -->
      <div class="flex gap-3">
        <button
          v-if="mode === 'login'"
          @click="emit('close')"
          class="flex-1 py-2 px-4 text-sm font-medium rounded-lg transition"
          style="color: var(--text-2); background: var(--surface-hover);"
        >
          Cancel
        </button>
        <button
          @click="submit"
          :disabled="loading || digits.some(d => d === '')"
          class="flex-1 py-2 px-4 text-sm font-medium text-white bg-[var(--brand-primary)] hover:bg-[var(--brand-primary-dark)] rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <span v-if="loading" class="inline-flex items-center gap-2">
            <svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24" aria-hidden="true">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            Verifying…
          </span>
          <span v-else>Verify</span>
        </button>
      </div>

      <!-- Help text for setup -->
      <p v-if="mode === 'setup'" class="text-[11px] text-center mt-4" style="color: var(--text-3);">
        Use Google Authenticator, Authy, or any TOTP-compatible app
      </p>
    </div>
  </div>
</template>
