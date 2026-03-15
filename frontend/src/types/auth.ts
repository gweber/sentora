/** Auth domain types. */

export type AccountStatus = 'invited' | 'active' | 'suspended' | 'deactivated' | 'deleted'

export interface LoginRequest {
  username: string
  password: string
  totp_code?: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
  role?: 'super_admin' | 'admin' | 'analyst' | 'viewer'
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  requires_totp: boolean
}

export interface RefreshRequest {
  refresh_token: string
}

export interface TotpSetupResponse {
  user: UserInfo
  totp_uri: string
  qr_code_svg: string
}

export interface TotpVerifySetupRequest {
  username: string
  password: string
  code: string
}

export interface ChangePasswordRequest {
  current_password: string
  new_password: string
}

export interface UserInfo {
  id: string
  username: string
  email: string
  role: 'super_admin' | 'admin' | 'analyst' | 'viewer'
  disabled: boolean
  totp_enabled: boolean
  status: AccountStatus
}

export interface UsersListResponse {
  users: UserInfo[]
  total: number
}

export interface OIDCLoginResponse {
  authorization_url: string
}

export interface SessionInfo {
  id: string
  username: string
  created_at: string
  last_active_at: string
  expires_at: string
  ip_address: string
  user_agent: string
  is_active: boolean
  is_current: boolean
  revoked_at: string | null
  revoked_reason: string | null
}

export interface SessionsListResponse {
  sessions: SessionInfo[]
  total: number
}

export interface PasswordPolicy {
  min_length: number
  require_uppercase: boolean
  require_lowercase: boolean
  require_digit: boolean
  require_special: boolean
  history_count: number
  max_age_days: number | null
  check_breached: boolean
}
