const defaultAppPath = '/app/prompts';

export function sanitizeReturnTo(value: string | null | undefined): string {
  if (!value || (value !== '/app' && !value.startsWith('/app/')) || value.startsWith('//')) return defaultAppPath;
  return value;
}

export function getReturnTo(search: string): string {
  return sanitizeReturnTo(new URLSearchParams(search).get('returnTo'));
}

export function getLoginPath(returnTo: string): string {
  return `/login?returnTo=${encodeURIComponent(sanitizeReturnTo(returnTo))}`;
}

export function getChangePasswordPath(returnTo: string): string {
  return `/change-password?returnTo=${encodeURIComponent(sanitizeReturnTo(returnTo))}`;
}
