import { ref, readonly } from 'vue'
import { getBranding } from '@/api/config'
import type { Branding } from '@/types/config'

const brandName = ref('Sentora')
const brandTagline = ref('EDR Asset Classification')
const brandPrimaryColor = ref('#6366f1')
const brandLogoUrl = ref('')
const brandFaviconUrl = ref('')
const loaded = ref(false)

/**
 * Convert a hex color (#RRGGBB or #RGB) to R,G,B string for use with
 * rgb() / rgba() in CSS custom properties.
 */
function hexToRgb(hex: string): string {
  let h = hex.replace('#', '')
  if (h.length === 3) {
    h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2]
  }
  const r = parseInt(h.substring(0, 2), 16)
  const g = parseInt(h.substring(2, 4), 16)
  const b = parseInt(h.substring(4, 6), 16)
  return `${r}, ${g}, ${b}`
}

/**
 * Lighten or darken a hex color by a percentage (-100 to +100).
 */
function adjustColor(hex: string, percent: number): string {
  let h = hex.replace('#', '')
  if (h.length === 3) {
    h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2]
  }
  const r = Math.min(255, Math.max(0, parseInt(h.substring(0, 2), 16) + Math.round(2.55 * percent)))
  const g = Math.min(255, Math.max(0, parseInt(h.substring(2, 4), 16) + Math.round(2.55 * percent)))
  const b = Math.min(255, Math.max(0, parseInt(h.substring(4, 6), 16) + Math.round(2.55 * percent)))
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
}

function applyBrandingToDOM(color: string, name: string, faviconUrl: string): void {
  const root = document.documentElement.style
  root.setProperty('--brand-primary', color)
  root.setProperty('--brand-primary-rgb', hexToRgb(color))
  root.setProperty('--brand-primary-light', adjustColor(color, 20))
  root.setProperty('--brand-primary-dark', adjustColor(color, -15))

  document.title = name

  if (faviconUrl) {
    let link = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
    if (!link) {
      link = document.createElement('link')
      link.rel = 'icon'
      document.head.appendChild(link)
    }
    link.href = faviconUrl
  }
}

/**
 * Composable that provides reactive branding state.
 * Fetches branding from the public API on first call and applies CSS custom properties.
 */
export function useBranding() {
  async function loadBranding(): Promise<void> {
    if (loaded.value) return
    try {
      const branding: Branding = await getBranding()
      brandName.value = branding.app_name
      brandTagline.value = branding.tagline
      brandPrimaryColor.value = branding.primary_color
      brandLogoUrl.value = branding.logo_url
      brandFaviconUrl.value = branding.favicon_url
      applyBrandingToDOM(branding.primary_color, branding.app_name, branding.favicon_url)
      loaded.value = true
    } catch {
      // Use defaults if branding endpoint unavailable
      applyBrandingToDOM(brandPrimaryColor.value, brandName.value, '')
      loaded.value = true
    }
  }

  /** Re-apply branding after a config update (e.g., from Settings view). */
  function updateBranding(branding: Partial<Branding>): void {
    if (branding.app_name !== undefined) brandName.value = branding.app_name
    if (branding.tagline !== undefined) brandTagline.value = branding.tagline
    if (branding.primary_color !== undefined) brandPrimaryColor.value = branding.primary_color
    if (branding.logo_url !== undefined) brandLogoUrl.value = branding.logo_url
    if (branding.favicon_url !== undefined) brandFaviconUrl.value = branding.favicon_url
    applyBrandingToDOM(brandPrimaryColor.value, brandName.value, brandFaviconUrl.value)
  }

  function reset(): void {
    brandName.value = 'Sentora'
    brandTagline.value = 'EDR Asset Classification'
    brandPrimaryColor.value = '#6366f1'
    brandLogoUrl.value = ''
    brandFaviconUrl.value = ''
    loaded.value = false
  }

  return {
    brandName: readonly(brandName),
    brandTagline: readonly(brandTagline),
    brandPrimaryColor: readonly(brandPrimaryColor),
    brandLogoUrl: readonly(brandLogoUrl),
    brandFaviconUrl: readonly(brandFaviconUrl),
    loaded: readonly(loaded),
    loadBranding,
    updateBranding,
    reset,
  }
}
