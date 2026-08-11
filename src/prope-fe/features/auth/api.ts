import { sessionSchema, type LoginCredentials, type Session } from '@/features/auth/types';

const sessionKey = 'prope.mock-session';
const mockEmail = 'demo@prope.ai';
const mockPassword = 'prope-demo';

const wait = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

export async function getSession(): Promise<Session | null> {
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

export async function login(credentials: LoginCredentials): Promise<Session> {
  await wait(650);
  if (credentials.email.toLowerCase() !== mockEmail || credentials.password !== mockPassword) {
    throw new Error('INVALID_CREDENTIALS');
  }
  const session: Session = {
    id: crypto.randomUUID(),
    expiresAt: new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString(),
    user: {
      id: 'user-linh',
      displayName: 'Linh Nguyễn',
      email: mockEmail,
      role: 'owner',
      workspaceName: 'Prope workspace',
    },
  };
  window.localStorage.setItem(sessionKey, JSON.stringify(session));
  return session;
}

export async function logout(): Promise<void> {
  await wait(220);
  window.localStorage.removeItem(sessionKey);
}
