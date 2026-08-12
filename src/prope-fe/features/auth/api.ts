import { apiRequest, isApiError } from '@/lib/apiClient';
import {
  sessionResponseSchema,
  type ChangePasswordCredentials,
  type LoginCredentials,
  type Session,
  type SignupCredentials,
} from '@/features/auth/types';

/**
 * INT-029's `/auth` surface, called directly.
 *
 * **There is no mock mode any more, and its removal is the point.** This module
 * used to answer from `localStorage` whenever `import.meta.env.DEV` was set,
 * which meant `pnpm dev` never once exercised the real sign-in — so the contract
 * drift between the two sides (a login body that did not parse, a `/auth/session`
 * route that did not exist, a `Secure` cookie the dev origin discards) was
 * invisible until deployment. A fixture that only runs where nobody is looking is
 * a fixture that hides the bug it would have caught.
 *
 * The dev server proxies `/api` to the application (see `vite.config.ts`), so
 * these paths are same-origin in development exactly as they are behind Caddy —
 * which is what lets the session cookie be `SameSite=Lax` with no CORS
 * configuration and no CSRF token anywhere in Prope (A-142 §8, ADR-0052).
 */

export async function getSession(): Promise<Session | null> {
  try {
    return await apiRequest('/api/v1/auth/session', {
      schema: sessionResponseSchema,
      // A `401` here is the ordinary signed-out state, not a session that just
      // expired under somebody's feet — this is the request that *asks*. Letting
      // it fire the unauthorized handler would bounce a first-time visitor to the
      // sign-in screen with a "your session expired" banner they never had.
      notifyUnauthorized: false,
    });
  } catch (error) {
    if (isApiError(error) && error.status === 401) return null;
    throw error;
  }
}

export function login(credentials: LoginCredentials): Promise<Session> {
  return apiRequest('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify(credentials),
    schema: sessionResponseSchema,
    // The `401` here IS the answer — wrong credentials — and the form renders it.
    // The global handler would navigate away from the screen showing the error.
    notifyUnauthorized: false,
  });
}

export function signup(credentials: SignupCredentials): Promise<Session> {
  return apiRequest('/api/v1/auth/register', {
    method: 'POST',
    body: JSON.stringify({
      display_name: credentials.displayName,
      email: credentials.email,
      password: credentials.password,
    }),
    schema: sessionResponseSchema,
    notifyUnauthorized: false,
  });
}

export async function logout(): Promise<void> {
  try {
    await apiRequest('/api/v1/auth/logout', { method: 'POST', notifyUnauthorized: false });
  } catch (error) {
    // Signing out of a session the server has already ended is the outcome the
    // caller wanted. Anything else is a real failure and the account panel offers
    // a retry.
    if (!isApiError(error) || error.status !== 401) throw error;
  }
}

export function changePassword(credentials: ChangePasswordCredentials): Promise<void> {
  return apiRequest('/api/v1/auth/password', {
    method: 'POST',
    body: JSON.stringify({
      current_password: credentials.currentPassword,
      new_password: credentials.newPassword,
    }),
    notifyUnauthorized: true,
  });
}
