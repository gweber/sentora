/**
 * Export domain API calls.
 *
 * Provides functions for the CPE-enriched software inventory export.
 */

import client from './client'

/** Export software inventory as JSON. */
export async function exportSoftwareInventory(params?: {
  format?: 'json' | 'csv'
  include_eol?: boolean
  include_cpe?: boolean
  scope_groups?: string
  scope_tags?: string
  classification?: string
  page?: number
  page_size?: number
}): Promise<unknown> {
  if (params?.format === 'csv') {
    const { data } = await client.get('/export/software-inventory', {
      params: { ...params },
      responseType: 'blob',
    })
    return data
  }
  const { data } = await client.get('/export/software-inventory', { params })
  return data
}
