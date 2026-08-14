import { ApiError, apiRequest, isApiError } from '@/lib/apiClient';
import { sessionResponseSchema, sessionSchema, type ChangePasswordCredentials, type LoginCredentials, type Session, type SignupCredentials } from '@/features/auth/types';

const sessionKey = 'prope.mock-session';
const mockEmail = 'demo@prope.ai';
const mockPassword = 'prope-demo';
const mockFirstLoginEmail = 'new@prope.ai';
const mockFirstLoginPassword = 'prope-first';
const authMode = import.meta.env.VITE_AUTH_MODE ?? (import.meta.env.DEV ? 'mock' : 'api');

const wait = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));
const createMockId = () => crypto.randomUUID?.() ?? `${Date.now().toString(36)}_${Math.random().toString(36).slice(2)}`;

async function getMockSession(): Promise<Session | null> {
  await wait(180);
  const stored = window.localStorage.getItem(sessionKey);
  if (!stored) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(stored);
  } catch {
    window.localStorage.removeItem(sessionKey);
    return null;
  }
  const result = sessionSchema.safeParse(parsed);
  if (!result.success || new Date(result.data.expiresAt) <= new Date()) {
    window.localStorage.removeItem(sessionKey);
    return null;
  }
  return result.data;
}

async function mockLogin(credentials: LoginCredentials): Promise<Session> {
  await wait(650);
  const email = credentials.email.toLowerCase();
  const validDemo = email === mockEmail && credentials.password === mockPassword;
  const validFirstLogin = email === mockFirstLoginEmail && credentials.password === mockFirstLoginPassword;
  if (!validDemo && !validFirstLogin) {
    throw new ApiError(401, 'INVALID_CREDENTIALS', 'Invalid credentials');
  }
  const session: Session = {
    id: `ses_${createMockId()}`,
    expiresAt: new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString(),
    mustChangePassword: validFirstLogin,
    user: {
      id: validFirstLogin ? 'usr_new' : 'usr_linh',
      displayName: validFirstLogin ? 'Thành viên mới' : 'Linh Nguyễn',
      email,
      role: 'owner',
      workspaceName: 'Prope workspace',
    },
  };
  window.localStorage.setItem(sessionKey, JSON.stringify(session));
  return session;
}

async function mockSignup(credentials: SignupCredentials): Promise<Session> {
  await wait(650);
  const email = credentials.email.toLowerCase();
  if (email === mockEmail || email === mockFirstLoginEmail || email === 'existing@prope.ai') {
    throw new ApiError(409, 'EMAIL_ALREADY_EXISTS', 'Email already exists');
  }
  const session: Session = {
    id: `ses_${createMockId()}`,
    expiresAt: new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString(),
    mustChangePassword: false,
    user: {
      id: `usr_${createMockId()}`,
      displayName: credentials.displayName,
      email,
      role: 'owner',
      workspaceName: 'Prope workspace',
    },
  };
  window.localStorage.setItem(sessionKey, JSON.stringify(session));
  return session;
}

async function mockLogout(): Promise<void> {
  await wait(220);
  window.localStorage.removeItem(sessionKey);
}

async function mockChangePassword(credentials: ChangePasswordCredentials): Promise<void> {
  await wait(420);
  const session = await getMockSession();
  if (!session) throw new ApiError(401, 'UNAUTHENTICATED', 'Session expired');
  if (credentials.currentPassword !== mockFirstLoginPassword) throw new ApiError(400, 'INVALID_CURRENT_PASSWORD', 'Invalid current password');
  window.localStorage.setItem(sessionKey, JSON.stringify({ ...session, mustChangePassword: false }));
}

export async function getSession(): Promise<Session | null> {
  if (authMode === 'mock') return getMockSession();
  try {
    return await apiRequest('/api/v1/auth/session', { schema: sessionResponseSchema, notifyUnauthorized: false });
  } catch (error) {
    if (isApiError(error) && error.status === 401) return null;
    throw error;
  }
}

export function login(credentials: LoginCredentials): Promise<Session> {
  if (authMode === 'mock') return mockLogin(credentials);
  return apiRequest('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify(credentials),
    schema: sessionResponseSchema,
    notifyUnauthorized: false,
  });
}

export function signup(credentials: SignupCredentials): Promise<Session> {
  if (authMode === 'mock') return mockSignup(credentials);
  return apiRequest('/api/v1/auth/register', {
    method: 'POST',
    body: JSON.stringify({ display_name: credentials.displayName, email: credentials.email, password: credentials.password }),
    schema: sessionResponseSchema,
    notifyUnauthorized: false,
  });
}

export async function logout(): Promise<void> {
  if (authMode === 'mock') return mockLogout();
  try {
    await apiRequest('/api/v1/auth/logout', { method: 'POST', notifyUnauthorized: false });
  } catch (error) {
    if (!isApiError(error) || error.status !== 401) throw error;
  }
}

export function changePassword(credentials: ChangePasswordCredentials): Promise<void> {
  if (authMode === 'mock') return mockChangePassword(credentials);
  return apiRequest('/api/v1/auth/password', {
    method: 'POST',
    body: JSON.stringify({ current_password: credentials.currentPassword, new_password: credentials.newPassword }),
    notifyUnauthorized: true,
  });
}
