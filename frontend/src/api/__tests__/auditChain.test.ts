import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

import client from '@/api/client'
import {
  getChainStatus,
  verifyChain,
  listEpochs,
  exportEpoch,
  initializeChain,
} from '@/api/auditChain'
import type { ChainStatusResponse, VerifyChainResponse, EpochListResponse } from '@/api/auditChain'

const mockStatus: ChainStatusResponse = {
  total_entries: 1500,
  current_epoch: 1,
  current_sequence: 1499,
  genesis_hash: 'abc123def456',
  latest_hash: '789xyz000111',
  chain_valid: true,
  last_verified_at: '2026-03-15T12:00:00Z',
}

const mockVerifyResult: VerifyChainResponse = {
  status: 'valid',
  verified_entries: 1500,
  first_sequence: 0,
  last_sequence: 1499,
  epochs_verified: 1,
  broken_at_sequence: null,
  broken_reason: null,
  verification_time_ms: 234,
}

const mockEpochList: EpochListResponse = {
  epochs: [
    {
      epoch: 0,
      first_sequence: 0,
      last_sequence: 999,
      entry_count: 1000,
      first_timestamp: '2026-03-01T00:00:00Z',
      last_timestamp: '2026-03-07T23:59:59Z',
      epoch_final_hash: 'epoch0hash',
      previous_epoch_hash: null,
      exported: false,
    },
  ],
  total: 1,
}

describe('auditChain API', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('getChainStatus calls GET /audit/chain/status', async () => {
    vi.mocked(client.get).mockResolvedValue({ data: mockStatus })
    const result = await getChainStatus()
    expect(client.get).toHaveBeenCalledWith('/audit/chain/status')
    expect(result.total_entries).toBe(1500)
    expect(result.chain_valid).toBe(true)
  })

  it('verifyChain calls POST /audit/chain/verify with body', async () => {
    vi.mocked(client.post).mockResolvedValue({ data: mockVerifyResult })
    const result = await verifyChain({ epoch: null })
    expect(client.post).toHaveBeenCalledWith('/audit/chain/verify', { epoch: null })
    expect(result.status).toBe('valid')
    expect(result.verified_entries).toBe(1500)
  })

  it('verifyChain can verify single epoch', async () => {
    vi.mocked(client.post).mockResolvedValue({ data: mockVerifyResult })
    await verifyChain({ epoch: 3 })
    expect(client.post).toHaveBeenCalledWith('/audit/chain/verify', { epoch: 3 })
  })

  it('listEpochs calls GET /audit/chain/epochs', async () => {
    vi.mocked(client.get).mockResolvedValue({ data: mockEpochList })
    const result = await listEpochs()
    expect(client.get).toHaveBeenCalledWith('/audit/chain/epochs')
    expect(result.epochs).toHaveLength(1)
    expect(result.epochs[0]!.epoch).toBe(0)
  })

  it('exportEpoch calls POST /audit/chain/export/{epoch} with blob response', async () => {
    const mockBlob = new Blob(['test'], { type: 'application/json' })
    vi.mocked(client.post).mockResolvedValue({ data: mockBlob })
    const result = await exportEpoch(0)
    expect(client.post).toHaveBeenCalledWith('/audit/chain/export/0', null, {
      responseType: 'blob',
    })
    expect(result).toBe(mockBlob)
  })

  it('initializeChain calls POST /audit/chain/initialize', async () => {
    vi.mocked(client.post).mockResolvedValue({ data: {} })
    await initializeChain()
    expect(client.post).toHaveBeenCalledWith('/audit/chain/initialize')
  })
})
