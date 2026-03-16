import { ref, readonly, computed } from 'vue'
import axios from 'axios'

export interface DeploymentInfo {
  deployment_mode: 'onprem' | 'saas'
  multi_tenancy_enabled: boolean
  oidc_enabled: boolean
  saml_enabled: boolean
}

const info = ref<DeploymentInfo>({
  deployment_mode: 'onprem',
  multi_tenancy_enabled: false,
  oidc_enabled: false,
  saml_enabled: false,
})
const loaded = ref(false)

/**
 * Composable that provides reactive deployment mode information.
 * Fetches from the public /api/v1/deployment-info endpoint on first call.
 */
export function useDeployment() {
  async function loadDeploymentInfo(): Promise<void> {
    if (loaded.value) return
    try {
      const resp = await axios.get<DeploymentInfo>('/api/v1/deployment-info')
      info.value = resp.data
    } catch {
      // Use defaults (onprem) if endpoint unavailable
    }
    loaded.value = true
  }

  const isOnprem = computed(() => info.value.deployment_mode === 'onprem')
  const isSaas = computed(() => info.value.deployment_mode === 'saas')

  function reset(): void {
    info.value = {
      deployment_mode: 'onprem',
      multi_tenancy_enabled: false,
      oidc_enabled: false,
      saml_enabled: false,
    }
    loaded.value = false
  }

  return {
    deploymentMode: computed(() => info.value.deployment_mode),
    multiTenancyEnabled: computed(() => info.value.multi_tenancy_enabled),
    oidcEnabled: computed(() => info.value.oidc_enabled),
    samlEnabled: computed(() => info.value.saml_enabled),
    isOnprem,
    isSaas,
    loaded: readonly(loaded),
    loadDeploymentInfo,
    reset,
  }
}
