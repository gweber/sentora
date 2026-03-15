/**
 * Auth API — login, register, TOTP setup, token refresh, logout, sessions, password management.
 */

import client from './client'
import type {
  ChangePasswordRequest,
  LoginRequest,
  OIDCLoginResponse,
  PasswordPolicy,
  RefreshRequest,
  RegisterRequest,
  SessionsListResponse,
  TokenResponse,
  TotpSetupResponse,
  TotpVerifySetupRequest,
  UserInfo,
  UsersListResponse,
} from '@/types/auth'

export async function login(data: LoginRequest): Promise<TokenResponse> {
  const resp = await client.post<TokenResponse>('/auth/login', data)
  return resp.data
}

export async function register(data: RegisterRequest): Promise<TotpSetupResponse> {
  const resp = await client.post<TotpSetupResponse>('/auth/register', data)
  return resp.data
}

export async function verifyTotpSetup(data: TotpVerifySetupRequest): Promise<TokenResponse> {
  const resp = await client.post<TokenResponse>('/auth/totp/verify-setup', data)
  return resp.data
}

export async function refresh(data: RefreshRequest): Promise<TokenResponse> {
  const resp = await client.post<TokenResponse>('/auth/refresh', data)
  return resp.data
}

export async function logout(refreshToken: string): Promise<void> {
  await client.post('/auth/logout', { refresh_token: refreshToken })
}

export async function logoutAll(): Promise<void> {
  await client.post('/auth/logout/all')
}

export async function getMe(): Promise<UserInfo> {
  const resp = await client.get<UserInfo>('/auth/me')
  return resp.data
}

// ── Password management ─────────────────────────────────────────────────────

/** Change the current user's password. */
export async function changePassword(data: ChangePasswordRequest): Promise<void> {
  await client.post('/auth/change-password', data)
}

/** Get the current password policy. */
export async function getPasswordPolicy(): Promise<PasswordPolicy> {
  const resp = await client.get<PasswordPolicy>('/auth/password-policy')
  return resp.data
}

// ── Session management ──────────────────────────────────────────────────────

/** List the current user's active sessions. */
export async function listSessions(): Promise<SessionsListResponse> {
  const resp = await client.get<SessionsListResponse>('/auth/sessions')
  return resp.data
}

/** Revoke a specific session. */
export async function revokeSession(sessionId: string): Promise<void> {
  await client.delete(`/auth/sessions/${sessionId}`)
}

/** Revoke all sessions except the current one. */
export async function revokeOtherSessions(): Promise<void> {
  await client.delete('/auth/sessions')
}

// ── User management (admin) ────────────────────────────────────────────────

export async function listUsers(): Promise<UsersListResponse> {
  const resp = await client.get<UsersListResponse>('/auth/users')
  return resp.data
}

export async function updateUserRole(username: string, role: string): Promise<UserInfo> {
  const resp = await client.patch<UserInfo>(`/auth/users/${username}/role`, { role })
  return resp.data
}

export async function updateUserDisabled(username: string, disabled: boolean): Promise<UserInfo> {
  const resp = await client.patch<UserInfo>(`/auth/users/${username}/disabled`, { disabled })
  return resp.data
}

export async function updateUserStatus(username: string, status: string, reason?: string): Promise<UserInfo> {
  const resp = await client.patch<UserInfo>(`/auth/users/${username}/status`, { status, reason })
  return resp.data
}

export async function deleteUser(username: string): Promise<void> {
  await client.delete(`/auth/users/${username}`)
}

// ── Admin session management ────────────────────────────────────────────────

/** List all sessions for a specific user (admin only). */
export async function adminListSessions(username: string): Promise<SessionsListResponse> {
  const resp = await client.get<SessionsListResponse>('/auth/admin/sessions', {
    params: { username },
  })
  return resp.data
}

/** Revoke all sessions for a specific user (admin only). */
export async function adminRevokeSessions(username: string): Promise<void> {
  await client.delete('/auth/admin/sessions', { params: { username } })
}

// ── OIDC / SSO ────────────────────────────────────────────────────────────

/** Get the OIDC authorization URL. Returns null if OIDC is not enabled (404). */
export async function getOidcLoginUrl(): Promise<string | null> {
  try {
    const resp = await client.get<OIDCLoginResponse>('/auth/oidc/login')
    return resp.data.authorization_url
  } catch {
    return null
  }
}

/** Exchange OIDC callback params for JWT tokens. */
export async function oidcCallback(code: string, state: string): Promise<TokenResponse> {
  const resp = await client.get<TokenResponse>('/auth/oidc/callback', {
    params: { code, state },
  })
  return resp.data
}

// ── SAML SSO ─────────────────────────────────────────────────────────────

/** Get the SAML redirect URL. Returns null if SAML is not enabled (404/501). */
export async function getSamlLoginUrl(): Promise<string | null> {
  try {
    const { data } = await client.get<{ redirect_url: string }>('/auth/saml/login')
    return data.redirect_url
  } catch {
    return null
  }
}

/** Exchange a one-time SAML nonce for JWT tokens. */
export async function samlExchange(nonce: string): Promise<TokenResponse> {
  const resp = await client.post<TokenResponse>('/auth/saml/exchange', null, {
    params: { nonce },
  })
  return resp.data
}
