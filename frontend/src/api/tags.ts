/**
 * Tags domain API calls.
 */

import type {
  S1TagsResponse,
  TagApplyResponse,
  TagPatternCreateRequest,
  TagPreviewResponse,
  TagRule,
  TagRuleCreateRequest,
  TagRulePattern,
  TagRuleUpdateRequest,
} from '@/types/tags'
import client from './client'

export async function listRules(): Promise<TagRule[]> {
  const { data } = await client.get<TagRule[]>('/tags/')
  return data
}

export async function getRule(ruleId: string): Promise<TagRule> {
  const { data } = await client.get<TagRule>(`/tags/${ruleId}`)
  return data
}

export async function createRule(payload: TagRuleCreateRequest): Promise<TagRule> {
  const { data } = await client.post<TagRule>('/tags/', payload)
  return data
}

export async function updateRule(
  ruleId: string,
  payload: TagRuleUpdateRequest,
): Promise<TagRule> {
  const { data } = await client.patch<TagRule>(`/tags/${ruleId}`, payload)
  return data
}

export async function deleteRule(ruleId: string): Promise<void> {
  await client.delete(`/tags/${ruleId}`)
}

export async function addPattern(
  ruleId: string,
  payload: TagPatternCreateRequest,
): Promise<TagRulePattern> {
  const { data } = await client.post<TagRulePattern>(`/tags/${ruleId}/patterns`, payload)
  return data
}

export async function removePattern(ruleId: string, patternId: string): Promise<void> {
  await client.delete(`/tags/${ruleId}/patterns/${patternId}`)
}

export async function previewRule(ruleId: string): Promise<TagPreviewResponse> {
  const { data } = await client.post<TagPreviewResponse>(`/tags/${ruleId}/preview`)
  return data
}

export async function applyRule(ruleId: string): Promise<TagApplyResponse> {
  const { data } = await client.post<TagApplyResponse>(`/tags/${ruleId}/apply`)
  return data
}

/** Fetch synced S1 tags from the last sync run */
export async function listSyncedTags(): Promise<S1TagsResponse> {
  const { data } = await client.get<S1TagsResponse>('/sync/tags')
  return data
}
