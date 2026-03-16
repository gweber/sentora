/**
 * Tags store.
 *
 * Manages tag rules, patterns, preview results, and apply state.
 * The tag editor drives most of this store's state.
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as tagsApi from '@/api/tags'
import type {
  TagApplyResponse,
  TagPatternCreateRequest,
  TagPreviewResponse,
  TagRule,
  TagRuleCreateRequest,
  TagRulePattern,
  TagRuleUpdateRequest,
} from '@/types/tags'

export const useTagStore = defineStore('tags', () => {
  const rules = ref<TagRule[]>([])
  const activeRule = ref<TagRule | null>(null)
  const previewResult = ref<TagPreviewResponse | null>(null)
  const isLoading = ref(false)
  const isPreviewLoading = ref(false)
  const isApplying = ref(false)
  const error = ref<string | null>(null)

  async function fetchRules(): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      rules.value = await tagsApi.listRules()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load tag rules'
    } finally {
      isLoading.value = false
    }
  }

  async function loadRule(ruleId: string): Promise<void> {
    isLoading.value = true
    error.value = null
    previewResult.value = null
    try {
      activeRule.value = await tagsApi.getRule(ruleId)
    } catch (err) {
      activeRule.value = null
      error.value = err instanceof Error ? err.message : 'Failed to load tag rule'
    } finally {
      isLoading.value = false
    }
  }

  async function createRule(payload: TagRuleCreateRequest): Promise<TagRule | null> {
    error.value = null
    try {
      const rule = await tagsApi.createRule(payload)
      rules.value.push(rule)
      return rule
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to create tag rule'
      return null
    }
  }

  async function updateRule(ruleId: string, payload: TagRuleUpdateRequest): Promise<void> {
    error.value = null
    try {
      const updated = await tagsApi.updateRule(ruleId, payload)
      activeRule.value = updated
      const idx = rules.value.findIndex((r) => r.id === ruleId)
      if (idx !== -1) rules.value[idx] = updated
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to update tag rule'
    }
  }

  async function deleteRule(ruleId: string): Promise<void> {
    error.value = null
    try {
      await tagsApi.deleteRule(ruleId)
      rules.value = rules.value.filter((r) => r.id !== ruleId)
      if (activeRule.value?.id === ruleId) activeRule.value = null
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to delete tag rule'
    }
  }

  async function addPattern(
    ruleId: string,
    payload: TagPatternCreateRequest,
  ): Promise<TagRulePattern | null> {
    error.value = null
    try {
      const pattern = await tagsApi.addPattern(ruleId, payload)
      if (activeRule.value?.id === ruleId) {
        activeRule.value = { ...activeRule.value, patterns: [...activeRule.value.patterns, pattern] }
      }
      return pattern
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to add pattern'
      return null
    }
  }

  async function removePattern(ruleId: string, patternId: string): Promise<void> {
    error.value = null
    try {
      await tagsApi.removePattern(ruleId, patternId)
      if (activeRule.value?.id === ruleId) {
        activeRule.value = {
          ...activeRule.value,
          patterns: activeRule.value.patterns.filter((p) => p.id !== patternId),
        }
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to remove pattern'
    }
  }

  async function previewRule(ruleId: string): Promise<void> {
    isPreviewLoading.value = true
    error.value = null
    try {
      previewResult.value = await tagsApi.previewRule(ruleId)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Preview failed'
    } finally {
      isPreviewLoading.value = false
    }
  }

  async function applyRule(ruleId: string): Promise<TagApplyResponse | null> {
    isApplying.value = true
    error.value = null
    try {
      const result = await tagsApi.applyRule(ruleId)
      // Refresh active rule to pick up new apply_status
      if (activeRule.value?.id === ruleId) {
        activeRule.value = await tagsApi.getRule(ruleId)
      }
      return result
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Apply failed'
      return null
    } finally {
      isApplying.value = false
    }
  }

  return {
    rules,
    activeRule,
    previewResult,
    isLoading,
    isPreviewLoading,
    isApplying,
    error,
    fetchRules,
    loadRule,
    createRule,
    updateRule,
    deleteRule,
    addPattern,
    removePattern,
    previewRule,
    applyRule,
  }
})
