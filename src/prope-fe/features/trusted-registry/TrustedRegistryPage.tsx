import { ArrowClockwise } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { PreservationShell } from '@/features/preservation/components/PreservationShell';
import { registryListOptions } from '@/features/trusted-registry/api';
import { RegistryEmptyState } from '@/features/trusted-registry/components/RegistryEmptyState';
import { RegistryFilters } from '@/features/trusted-registry/components/RegistryFilters';
import { RegistryPromptCard } from '@/features/trusted-registry/components/RegistryPromptCard';
import { useRegistryFilters } from '@/features/trusted-registry/useRegistryFilters';

export function TrustedRegistryPage() {
  const { t } = useTranslation();
  const registry = useQuery(registryListOptions);
  const filters = useRegistryFilters(registry.data ?? []);
  return (
    <PreservationShell activeId="registry" title={t('trustedRegistry.title')} description={t('trustedRegistry.description')}>
      {registry.isPending ? <div className="space-y-6" aria-label={t('common.loading')}><div className="h-44 animate-pulse rounded-modal bg-subtle motion-reduce:animate-none" /><div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{[0, 1, 2].map((item) => <div key={item} className="h-72 animate-pulse rounded-modal bg-subtle motion-reduce:animate-none" />)}</div></div> : null}
      {registry.isError ? <section role="alert" className="grid min-h-80 place-items-center rounded-panel border border-danger-strong bg-danger p-6 text-center"><div><h2 className="text-heading-2 font-semibold">{t('trustedRegistry.error.title')}</h2><p className="mt-2 text-body text-danger-text">{t('trustedRegistry.error.body')}</p><Button intent="neutral" className="mt-5" leadingIcon={<ArrowClockwise aria-hidden className="size-4" />} onClick={() => void registry.refetch()}>{t('trustedRegistry.actions.retry')}</Button></div></section> : null}
      {registry.data ? <div className="space-y-6"><RegistryFilters prompts={registry.data} filters={filters} /><div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-overline font-semibold text-muted">{t('trustedRegistry.results.eyebrow')}</p><h2 className="mt-1 text-heading-2 font-semibold">{t('trustedRegistry.results.count', { count: filters.visiblePrompts.length })}</h2></div><p className="text-caption text-muted">{t('trustedRegistry.results.guidance')}</p></div><div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{filters.visiblePrompts.length ? filters.visiblePrompts.map((prompt) => <RegistryPromptCard key={prompt.id} prompt={prompt} />) : <RegistryEmptyState filtered={filters.filtered} onClear={filters.clear} />}</div></div> : null}
    </PreservationShell>
  );
}

