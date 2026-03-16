import axios from 'axios'
import client from './client'
import type { AppConfig, AppConfigUpdate, Branding } from '@/types/config'

export async function getConfig(): Promise<AppConfig> {
  const { data } = await client.get<AppConfig>('/config/')
  return data
}

export async function updateConfig(payload: AppConfigUpdate): Promise<AppConfig> {
  const { data } = await client.put<AppConfig>('/config/', payload)
  return data
}

/**
 * Fetch public branding configuration (no auth required).
 * Uses raw axios instead of the intercepted client so it works before login.
 */
export async function getBranding(): Promise<Branding> {
  const { data } = await axios.get<Branding>('/api/v1/branding/')
  return data
}
