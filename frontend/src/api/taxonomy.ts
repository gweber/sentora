/**
 * Taxonomy API calls.
 */

import type {
  CategoryCreateRequest,
  CategoryDeleteResponse,
  CategoryListResponse,
  CategorySummary,
  CategoryUpdateRequest,
  CategoryUpdateResponse,
  PatternPreviewRequest,
  PatternPreviewResponse,
  SoftwareEntry,
  SoftwareEntryCreateRequest,
  SoftwareEntryListResponse,
  SoftwareEntryUpdateRequest,
} from '@/types/taxonomy'
import client from './client'

/** List all taxonomy categories with entry counts. */
export async function listCategories(): Promise<CategoryListResponse> {
  const { data } = await client.get<CategoryListResponse>('/taxonomy/')
  return data
}

/** Create a new taxonomy category. */
export async function createCategory(payload: CategoryCreateRequest): Promise<CategorySummary> {
  const { data } = await client.post<CategorySummary>('/taxonomy/category', payload)
  return data
}

/** Get all entries in a specific category. */
export async function getEntriesByCategory(category: string): Promise<SoftwareEntryListResponse> {
  const { data } = await client.get<SoftwareEntryListResponse>(`/taxonomy/category/${category}`)
  return data
}

/** Search taxonomy entries by name. */
export async function searchTaxonomy(query: string, limit = 50): Promise<SoftwareEntryListResponse> {
  const { data } = await client.get<SoftwareEntryListResponse>('/taxonomy/search', {
    params: { q: query, limit },
  })
  return data
}

/** Get a single taxonomy entry by ID. */
export async function getEntry(entryId: string): Promise<SoftwareEntry> {
  const { data } = await client.get<SoftwareEntry>(`/taxonomy/${entryId}`)
  return data
}

/** Add a new taxonomy entry. */
export async function addEntry(payload: SoftwareEntryCreateRequest): Promise<SoftwareEntry> {
  const { data } = await client.post<SoftwareEntry>('/taxonomy/', payload)
  return data
}

/** Partially update a taxonomy entry. */
export async function editEntry(
  entryId: string,
  payload: SoftwareEntryUpdateRequest,
): Promise<SoftwareEntry> {
  const { data } = await client.patch<SoftwareEntry>(`/taxonomy/${entryId}`, payload)
  return data
}

/** Delete a taxonomy entry. */
export async function deleteEntry(entryId: string): Promise<void> {
  await client.delete(`/taxonomy/${entryId}`)
}

/** Toggle the universal exclusion flag on an entry. */
export async function toggleUniversal(entryId: string): Promise<SoftwareEntry> {
  const { data } = await client.post<SoftwareEntry>(
    `/taxonomy/${entryId}/toggle-universal`,
  )
  return data
}

/** Rename a category's key and/or display label. */
export async function updateCategory(
  categoryKey: string,
  payload: CategoryUpdateRequest,
): Promise<CategoryUpdateResponse> {
  const { data } = await client.patch<CategoryUpdateResponse>(
    `/taxonomy/category/${categoryKey}`,
    payload,
  )
  return data
}

/** Delete a category and all its entries. */
export async function deleteCategory(categoryKey: string): Promise<CategoryDeleteResponse> {
  const { data } = await client.delete<CategoryDeleteResponse>(
    `/taxonomy/category/${categoryKey}`,
  )
  return data
}

/** Preview which agents/apps would match a glob pattern. */
export async function previewPattern(
  payload: PatternPreviewRequest,
): Promise<PatternPreviewResponse> {
  const { data } = await client.post<PatternPreviewResponse>('/taxonomy/preview', payload)
  return data
}
