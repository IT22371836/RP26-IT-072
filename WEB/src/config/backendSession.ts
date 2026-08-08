import { ApiError, backendApi } from './api';
import type { BackendTokenResponse, BackendUser } from './api';
import { runtimeConfig } from './runtime';

const BACKEND_SESSION_KEY = 'weda_backend_session_v2';

function storeBackendSession(session: BackendTokenResponse): void {
  localStorage.setItem(BACKEND_SESSION_KEY, JSON.stringify(session));
}

export function readBackendSession(): BackendTokenResponse | null {
  const raw = localStorage.getItem(BACKEND_SESSION_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as BackendTokenResponse;
  } catch {
    localStorage.removeItem(BACKEND_SESSION_KEY);
    return null;
  }
}

export function clearBackendSession(): void {
  localStorage.removeItem(BACKEND_SESSION_KEY);
}

export async function logoutBackendSession(): Promise<void> {
  try {
    await backendApi.logout();
  } finally {
    clearBackendSession();
  }
}

export function requireBackendToken(): string {
  const session = readBackendSession();
  if (session?.token_transport === 'cookie' && session.user) return '';
  if (!session?.access_token) {
    throw new Error('A linked FastAPI session is required for this operation. Please sign in again.');
  }
  return session.access_token;
}

export function backendUserToWebUser(user: BackendUser): any {
  return {
    id: user.user_id,
    backendUserId: user.user_id,
    fullName: user.full_name,
    email: user.email,
    role: user.role,
    phone: '',
    district: '',
    city: '',
    preferredLanguage: 'English',
    location: { latitude: 6.9271, longitude: 79.8612 },
    createdAt: user.created_at,
    createdTimestamp: Date.parse(user.created_at)
  };
}

export async function loginBackendSession(
  email: string,
  password: string
): Promise<BackendTokenResponse> {
  const session = await backendApi.login(email.trim().toLowerCase(), password);
  storeBackendSession(session);
  return session;
}

export async function linkBackendSessionIfConfigured(
  email: string,
  password: string,
  firebaseIdToken?: string
): Promise<BackendTokenResponse | null> {
  if (runtimeConfig.authSource === 'firebase') {
    clearBackendSession();
    return null;
  }
  if (runtimeConfig.authSource === 'fastapi') {
    return loginBackendSession(email, password);
  }
  if (!firebaseIdToken) {
    throw new Error('A verified Firebase ID token is required to link this account.');
  }

  try {
    const session = await backendApi.linkFirebaseAccount(firebaseIdToken, password);
    storeBackendSession(session);
    return session;
  } catch (error) {
    // A previously linked account signs in with its established FastAPI password.
    if (!(error instanceof ApiError) || error.status !== 409) throw error;
    return loginBackendSession(email, password);
  }
}

export async function restoreBackendUser(): Promise<BackendUser | null> {
  const session = readBackendSession();
  if (!session) return null;
  try {
    const user = await backendApi.getCurrentUser(requireBackendToken());
    storeBackendSession({ ...session, user });
    return user;
  } catch {
    clearBackendSession();
    return null;
  }
}
