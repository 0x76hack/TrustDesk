export type UserRole = 'agent' | 'senior_agent' | 'admin';

export interface User {
  id: string;
  username: string;
  name: string;
  email: string;
  phone?: string;
  mfa_setup_completed?: boolean;
  is_primary_admin?: boolean;
  role: UserRole;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface MfaChallengeResponse {
  mfa_required: boolean;
  mfa_setup_required?: boolean;
  mfa_token: string;
  username: string;
  current_email?: string;
  current_phone?: string;
  expires_in_seconds?: number;
  dev_code?: string;
  message: string;
}

export interface OAuthLoginRequest {
  provider: 'google' | 'okta' | 'azure';
  email: string;
}

export interface UserProfileUpdate {
  name?: string;
  email?: string;
  phone?: string;
}

export interface PasswordChangeRequest {
  current_password: string;
  new_password: string;
}

export interface UserProvisionRequest {
  username: string;
  name: string;
  email: string;
  phone?: string;
  password?: string;
  role: UserRole;
}

export interface UserUpdateRequest {
  name?: string;
  email?: string;
  phone?: string;
  role?: UserRole;
  password?: string;
}

export interface SetupStatusResponse {
  is_initialized: boolean;
  admin_username: string | null;
  admin_email: string | null;
}

export interface PrimaryAdminSetupPayload {
  name: string;
  email: string;
  username: string;
  password: string;
  phone?: string;
  code?: string;
}

