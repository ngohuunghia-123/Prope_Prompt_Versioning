export type LifecycleOrigin = 'overview' | 'evaluation' | 'improvement';

export function lifecycleOrigin(value: string | null): LifecycleOrigin | undefined {
  return value === 'overview' || value === 'evaluation' || value === 'improvement' ? value : undefined;
}

export function internalReturnTo(value: string | null): string | undefined {
  if (!value || !value.startsWith('/app/') || value.startsWith('//')) return undefined;
  const parsed = new URL(value, 'https://prope.local');
  if (parsed.origin !== 'https://prope.local' || !parsed.pathname.startsWith('/app/')) return undefined;
  return `${parsed.pathname}${parsed.search}${parsed.hash}`;
}
