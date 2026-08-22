export type LifecycleOrigin = 'content' | 'overview' | 'evaluation' | 'improvement';

/** `overview` is kept for round-trips started before the Content tab rename. */
export function lifecycleOrigin(value: string | null): LifecycleOrigin | undefined {
  return value === 'content' || value === 'overview' || value === 'evaluation' || value === 'improvement' ? value : undefined;
}

export function internalReturnTo(value: string | null): string | undefined {
  if (!value || !value.startsWith('/app/') || value.startsWith('//')) return undefined;
  const parsed = new URL(value, 'https://prope.local');
  if (parsed.origin !== 'https://prope.local' || !parsed.pathname.startsWith('/app/')) return undefined;
  return `${parsed.pathname}${parsed.search}${parsed.hash}`;
}
