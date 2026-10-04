import { apiFetch, setAuthToken, removeAuthToken } from './client';
import type {
  LoginResponse,
  MfaChallengeResponse,
  UserProfileUpdate,
  UserProvisionRequest,
  User,
  SetupStatusResponse,
  PrimaryAdminSetupPayload,
} from '../types/auth';

export async function login(
  username: string,
  password: string,
  code?: string
): Promise<LoginResponse | MfaChallengeResponse> {
  const response = await apiFetch<LoginResponse | MfaChallengeResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password, code }),
  });

  if ('access_token' in response && response.access_token) {
    setAuthToken(response.access_token);
    sessionStorage.setItem('trustdesk_user', JSON.stringify(response.user));
  }
  return response;
}

export async function loginOAuth(
  provider: 'google' | 'okta' | 'azure',
  email: string
): Promise<MfaChallengeResponse> {
  return await apiFetch<MfaChallengeResponse>('/auth/oauth/login', {
    method: 'POST',
    body: JSON.stringify({ provider, email }),
  });
}

export async function verifyMfa(mfa_token: string, code: string): Promise<LoginResponse> {
  const response = await apiFetch<LoginResponse>('/auth/mfa/verify', {
    method: 'POST',
    body: JSON.stringify({ mfa_token, code }),
  });

  if (response.access_token) {
    setAuthToken(response.access_token);
    sessionStorage.setItem('trustdesk_user', JSON.stringify(response.user));
  }
  return response;
}

export async function setupSendOtp(
  setup_token: string,
  email: string,
  phone?: string
): Promise<{ message: string; expires_in_seconds: number; dev_code?: string }> {
  return await apiFetch<{ message: string; expires_in_seconds: number; dev_code?: string }>(
    '/auth/mfa/setup-send-otp',
    {
      method: 'POST',
      body: JSON.stringify({ setup_token, email, phone }),
    }
  );
}

export async function setupVerifyOtp(
  setup_token: string,
  email: string,
  code: string,
  phone?: string
): Promise<LoginResponse> {
  const response = await apiFetch<LoginResponse>('/auth/mfa/setup-verify-otp', {
    method: 'POST',
    body: JSON.stringify({ setup_token, email, code, phone }),
  });

  if (response.access_token) {
    setAuthToken(response.access_token);
    sessionStorage.setItem('trustdesk_user', JSON.stringify(response.user));
  }
  return response;
}

export async function resendLoginOtp(
  mfa_token: string
): Promise<{ message: string; expires_in_seconds: number; dev_code?: string }> {
  return await apiFetch<{ message: string; expires_in_seconds: number; dev_code?: string }>(
    '/auth/mfa/resend-login-otp',
    {
      method: 'POST',
      body: JSON.stringify({ mfa_token }),
    }
  );
}

export async function changePassword(
  data: import('../types/auth').PasswordChangeRequest
): Promise<{ message: string }> {
  return await apiFetch<{ message: string }>('/auth/change-password', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getProfile(): Promise<User> {
  return await apiFetch<User>('/auth/me');
}

export async function updateProfile(data: UserProfileUpdate): Promise<User> {
  const user = await apiFetch<User>('/auth/profile', {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
  sessionStorage.setItem('trustdesk_user', JSON.stringify(user));
  return user;
}

export async function provisionUser(data: UserProvisionRequest): Promise<User> {
  return await apiFetch<User>('/admin/users', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function listAdminUsers(): Promise<User[]> {
  return await apiFetch<User[]>('/admin/users');
}

export async function updateAdminUser(
  userId: string,
  data: import('../types/auth').UserUpdateRequest
): Promise<User> {
  return await apiFetch<User>(`/admin/users/${userId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteAdminUser(userId: string): Promise<{ message: string }> {
  return await apiFetch<{ message: string }>(`/admin/users/${userId}`, {
    method: 'DELETE',
  });
}

export function logout(): void {
  removeAuthToken();
  sessionStorage.removeItem('trustdesk_user');
  window.dispatchEvent(new CustomEvent('trustdesk:logout'));
}

export function getStoredUser(): User | null {
  const userStr = sessionStorage.getItem('trustdesk_user');
  if (!userStr) return null;
  try {
    return JSON.parse(userStr) as User;
  } catch {
    return null;
  }
}

export type { SetupStatusResponse, PrimaryAdminSetupPayload } from '../types/auth';

export async function getSetupStatus(): Promise<SetupStatusResponse> {
  return await apiFetch<SetupStatusResponse>('/auth/setup-status');
}

export async function setupPrimaryAdmin(
  payload: PrimaryAdminSetupPayload
): Promise<LoginResponse | { otp_required: boolean; email: string; expires_in_seconds: number; dev_code?: string; message: string }> {
  const response = await apiFetch<LoginResponse | { otp_required: boolean; email: string; expires_in_seconds: number; dev_code?: string; message: string }>(
    '/auth/setup-primary-admin',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    }
  );

  if ('access_token' in response && response.access_token) {
    setAuthToken(response.access_token);
    sessionStorage.setItem('trustdesk_user', JSON.stringify(response.user));
  }
  return response;
}

