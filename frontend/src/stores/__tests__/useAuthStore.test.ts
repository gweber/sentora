import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/useAuthStore'

vi.mock('@/api/auth', () => ({
  login: vi.fn(),
  register: vi.fn(),
  verifyTotpSetup: vi.fn(),
  getMe: vi.fn(),
  logout: vi.fn(),
  logoutAll: vi.fn(),
  oidcCallback: vi.fn(),
  changePassword: vi.fn(),
  listSessions: vi.fn(),
  revokeSession: vi.fn(),
  revokeOtherSessions: vi.fn(),
  getPasswordPolicy: vi.fn(),
}))

import * as authApi from '@/api/auth'
import type { UserInfo, TokenResponse, TotpSetupResponse } from '@/types/auth'

const mockUser: UserInfo = {
  id: 'u1',
  username: 'alice',
  email: 'alice@example.com',
  role: 'admin',
  disabled: false,
  totp_enabled: true,
  status: 'active',
}

const mockTokenResponse: TokenResponse = {
  access_token: 'access-123',
  refresh_token: 'refresh-456',
  token_type: 'bearer',
  requires_totp: false,
}

const mockTotpTokenResponse: TokenResponse = {
  access_token: '',
  refresh_token: '',
  token_type: 'bearer',
  requires_totp: true,
}

const mockTotpSetup: TotpSetupResponse = {
  user: mockUser,
  totp_uri: 'otpauth://totp/sentora:alice?secret=ABC',
  qr_code_svg: '<svg></svg>',
}

describe('useAuthStore', () => {
  let getItemSpy: ReturnType<typeof vi.spyOn>
  let setItemSpy: ReturnType<typeof vi.spyOn>
  let removeItemSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    // Mock localStorage before creating Pinia (store reads localStorage on creation)
    getItemSpy = vi.spyOn(Storage.prototype, 'getItem').mockReturnValue(null)
    setItemSpy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {})
    removeItemSpy = vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {})

    setActivePinia(createPinia())
    vi.resetAllMocks()

    // Re-apply localStorage mocks after resetAllMocks
    getItemSpy = vi.spyOn(Storage.prototype, 'getItem').mockReturnValue(null)
    setItemSpy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {})
    removeItemSpy = vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {})
  })

  describe('initial state', () => {
    it('starts with null user and no error', () => {
      const store = useAuthStore()
      expect(store.user).toBeNull()
      expect(store.error).toBeNull()
      expect(store.isLoading).toBe(false)
      expect(store.initialized).toBe(false)
      expect(store.pendingTotpSetup).toBeNull()
      expect(store.pendingTotpLogin).toBeNull()
    })

    it('reads token from localStorage on creation', () => {
      getItemSpy.mockImplementation((key: string) => {
        if (key === 'sentora_token') return 'stored-token'
        if (key === 'sentora_refresh_token') return 'stored-refresh'
        return null
      })
      setActivePinia(createPinia())

      const store = useAuthStore()
      expect(store.token).toBe('stored-token')
      expect(store.refreshToken).toBe('stored-refresh')
    })
  })

  describe('login', () => {
    it('sets tokens and fetches user on success', async () => {
      vi.mocked(authApi.login).mockResolvedValue(mockTokenResponse)
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser)

      const store = useAuthStore()
      const result = await store.login('alice', 'password')

      expect(result).toBe('ok')
      expect(store.token).toBe('access-123')
      expect(store.refreshToken).toBe('refresh-456')
      expect(store.user).toEqual(mockUser)
      expect(setItemSpy).toHaveBeenCalledWith('sentora_token', 'access-123')
      expect(setItemSpy).toHaveBeenCalledWith('sentora_refresh_token', 'refresh-456')
    })

    it('returns totp and sets pendingTotpLogin when requires_totp', async () => {
      vi.mocked(authApi.login).mockRejectedValue({
        response: { status: 401, data: { detail: { requires_totp: true } } },
        isAxiosError: true,
      })

      const store = useAuthStore()
      const result = await store.login('alice', 'password')

      expect(result).toBe('totp')
      expect(store.pendingTotpLogin).toEqual({ username: 'alice', password: 'password' })
      expect(store.user).toBeNull()
    })

    it('sets error on failure', async () => {
      vi.mocked(authApi.login).mockRejectedValue(new Error('Invalid credentials'))

      const store = useAuthStore()
      const result = await store.login('alice', 'wrong')

      expect(result).toBe('error')
      expect(store.error).toBe('Invalid credentials')
      expect(store.token).toBeNull()
      expect(store.user).toBeNull()
    })
  })

  describe('loginWithTotp', () => {
    it('returns false when no pendingTotpLogin', async () => {
      const store = useAuthStore()
      const result = await store.loginWithTotp('123456')
      expect(result).toBe(false)
    })

    it('sets tokens and fetches user on success', async () => {
      vi.mocked(authApi.login)
        .mockRejectedValueOnce({
          response: { status: 401, data: { detail: { requires_totp: true } } },
          isAxiosError: true,
        })
        .mockResolvedValueOnce(mockTokenResponse)
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser)

      const store = useAuthStore()
      await store.login('alice', 'password') // sets pendingTotpLogin

      const result = await store.loginWithTotp('123456')

      expect(result).toBe(true)
      expect(store.token).toBe('access-123')
      expect(store.user).toEqual(mockUser)
      expect(store.pendingTotpLogin).toBeNull()
      expect(authApi.login).toHaveBeenLastCalledWith({
        username: 'alice',
        password: 'password',
        totp_code: '123456',
      })
    })

    it('sets error on failure', async () => {
      vi.mocked(authApi.login)
        .mockRejectedValueOnce({
          response: { status: 401, data: { detail: { requires_totp: true } } },
          isAxiosError: true,
        })
        .mockRejectedValueOnce(new Error('Bad code'))
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser)

      const store = useAuthStore()
      await store.login('alice', 'password')

      const result = await store.loginWithTotp('000000')

      expect(result).toBe(false)
      expect(store.error).toBe('Bad code')
    })
  })

  describe('loginWithOidc', () => {
    it('sets tokens and fetches user on success', async () => {
      vi.mocked(authApi.oidcCallback).mockResolvedValue(mockTokenResponse)
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser)

      const store = useAuthStore()
      const result = await store.loginWithOidc('code-abc', 'state-xyz')

      expect(result).toBe(true)
      expect(store.token).toBe('access-123')
      expect(store.user).toEqual(mockUser)
      expect(authApi.oidcCallback).toHaveBeenCalledWith('code-abc', 'state-xyz')
    })

    it('sets error and returns false on failure', async () => {
      vi.mocked(authApi.oidcCallback).mockRejectedValue(new Error('SSO down'))

      const store = useAuthStore()
      const result = await store.loginWithOidc('code', 'state')

      expect(result).toBe(false)
      expect(store.error).toBe('SSO down')
      expect(store.token).toBeNull()
      expect(store.user).toBeNull()
    })
  })

  describe('register', () => {
    it('sets pendingTotpSetup on success', async () => {
      vi.mocked(authApi.register).mockResolvedValue(mockTotpSetup)

      const store = useAuthStore()
      const result = await store.register('alice', 'alice@example.com', 'password')

      expect(result).toBe(true)
      expect(store.pendingTotpSetup).toEqual(mockTotpSetup)
    })

    it('sets error on failure', async () => {
      vi.mocked(authApi.register).mockRejectedValue(new Error('Username taken'))

      const store = useAuthStore()
      const result = await store.register('alice', 'alice@example.com', 'password')

      expect(result).toBe(false)
      expect(store.error).toBe('Username taken')
    })
  })

  describe('verifyTotpSetup', () => {
    it('returns false when no pendingTotpSetup', async () => {
      const store = useAuthStore()
      const result = await store.verifyTotpSetup('123456')
      expect(result).toBe(false)
    })

    it('sets tokens and clears pending on success', async () => {
      vi.mocked(authApi.register).mockResolvedValue(mockTotpSetup)
      vi.mocked(authApi.verifyTotpSetup).mockResolvedValue(mockTokenResponse)
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser)

      const store = useAuthStore()
      await store.register('alice', 'alice@example.com', 'password')

      const result = await store.verifyTotpSetup('123456')

      expect(result).toBe(true)
      expect(store.token).toBe('access-123')
      expect(store.user).toEqual(mockUser)
      expect(store.pendingTotpSetup).toBeNull()
      expect(authApi.verifyTotpSetup).toHaveBeenCalledWith({
        username: 'alice',
        code: '123456',
        password: 'password',
      })
    })
  })

  describe('fetchUser', () => {
    it('clears tokens when getMe fails', async () => {
      vi.mocked(authApi.getMe).mockRejectedValue(new Error('Unauthorized'))

      const store = useAuthStore()
      // Manually set a token so fetchUser actually runs
      store.token = 'some-token'

      await store.fetchUser()

      expect(store.token).toBeNull()
      expect(store.user).toBeNull()
      expect(removeItemSpy).toHaveBeenCalledWith('sentora_token')
    })

    it('does nothing when no token', async () => {
      const store = useAuthStore()
      await store.fetchUser()
      expect(authApi.getMe).not.toHaveBeenCalled()
    })
  })

  describe('init', () => {
    it('only runs once', async () => {
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser)

      const store = useAuthStore()
      store.token = 'existing-token'

      await store.init()
      await store.init()

      expect(authApi.getMe).toHaveBeenCalledTimes(1)
      expect(store.initialized).toBe(true)
    })

    it('skips fetchUser when no token', async () => {
      const store = useAuthStore()
      await store.init()

      expect(authApi.getMe).not.toHaveBeenCalled()
      expect(store.initialized).toBe(true)
    })
  })

  describe('logout', () => {
    it('clears tokens, user, and pending state', async () => {
      vi.mocked(authApi.login).mockResolvedValue(mockTokenResponse)
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser)
      vi.mocked(authApi.logout).mockResolvedValue(undefined)

      const store = useAuthStore()
      await store.login('alice', 'password')

      await store.logout()

      expect(store.token).toBeNull()
      expect(store.refreshToken).toBeNull()
      expect(store.user).toBeNull()
      expect(store.pendingTotpSetup).toBeNull()
      expect(store.pendingTotpLogin).toBeNull()
      expect(removeItemSpy).toHaveBeenCalledWith('sentora_token')
      expect(removeItemSpy).toHaveBeenCalledWith('sentora_refresh_token')
    })

    it('clears locally even if server logout fails', async () => {
      vi.mocked(authApi.logout).mockRejectedValue(new Error('Server error'))

      const store = useAuthStore()
      store.token = 'tok'
      store.refreshToken = 'ref'

      await store.logout()

      expect(store.token).toBeNull()
      expect(store.user).toBeNull()
    })
  })

  describe('logoutAll', () => {
    it('clears tokens, user, and pending state', async () => {
      vi.mocked(authApi.logoutAll).mockResolvedValue(undefined)

      const store = useAuthStore()
      store.token = 'tok'
      store.user = mockUser

      await store.logoutAll()

      expect(store.token).toBeNull()
      expect(store.refreshToken).toBeNull()
      expect(store.user).toBeNull()
      expect(store.pendingTotpSetup).toBeNull()
      expect(store.pendingTotpLogin).toBeNull()
    })

    it('clears locally even if server logoutAll fails', async () => {
      vi.mocked(authApi.logoutAll).mockRejectedValue(new Error('Server error'))

      const store = useAuthStore()
      store.token = 'tok'

      await store.logoutAll()

      expect(store.token).toBeNull()
    })
  })

  describe('computed properties', () => {
    it('isAuthenticated is true when token and user are set', async () => {
      vi.mocked(authApi.login).mockResolvedValue(mockTokenResponse)
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser)

      const store = useAuthStore()
      expect(store.isAuthenticated).toBe(false)

      await store.login('alice', 'password')

      expect(store.isAuthenticated).toBe(true)
    })

    it('isAdmin is true for admin role', async () => {
      vi.mocked(authApi.login).mockResolvedValue(mockTokenResponse)
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser) // role: admin

      const store = useAuthStore()
      await store.login('alice', 'password')

      expect(store.isAdmin).toBe(true)
      expect(store.isAnalyst).toBe(true) // admin implies analyst
      expect(store.role).toBe('admin')
    })

    it('isAnalyst is true for analyst role but isAdmin is false', async () => {
      vi.mocked(authApi.login).mockResolvedValue(mockTokenResponse)
      vi.mocked(authApi.getMe).mockResolvedValue({
        ...mockUser,
        role: 'analyst',
      })

      const store = useAuthStore()
      await store.login('alice', 'password')

      expect(store.isAnalyst).toBe(true)
      expect(store.isAdmin).toBe(false)
      expect(store.role).toBe('analyst')
    })

    it('viewer has neither isAdmin nor isAnalyst', async () => {
      vi.mocked(authApi.login).mockResolvedValue(mockTokenResponse)
      vi.mocked(authApi.getMe).mockResolvedValue({
        ...mockUser,
        role: 'viewer',
      })

      const store = useAuthStore()
      await store.login('alice', 'password')

      expect(store.isAdmin).toBe(false)
      expect(store.isAnalyst).toBe(false)
      expect(store.role).toBe('viewer')
    })

    it('role is null when no user', () => {
      const store = useAuthStore()
      expect(store.role).toBeNull()
    })
  })
})
