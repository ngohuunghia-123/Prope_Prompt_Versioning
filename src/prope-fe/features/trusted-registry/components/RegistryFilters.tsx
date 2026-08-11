import { MagnifyingGlass } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import type { RegistryPrompt } from '@/features/trusted-registry/types';
import type { useRegistryFilters } from '@/features/trusted-registry/useRegistryFilters';

export interface RegistryFiltersProps {
  prompts: RegistryPrompt[];
  filters: ReturnType<typeof useRegistryFilters>;
}

export function RegistryFilters({ prompts, filters }: RegistryFiltersProps) {
  const { t } = useTranslation();
  const options = (values: string[], allLabel: string) => [{ value: 'all', label: allLabel }, ...Array.from(new Set(values)).map((value) => ({ value, label: value }))];
  return (
    <section aria-label={t('trustedRegistry.filters.label')} className="rounded-modal border border-border bg-surface p-4 shadow-floating sm:p-5">
      <div className="relative">
        <MagnifyingGlass aria-hidden className="pointer-events-none absolute right-3 top-9 size-5 text-muted" />
        <Input label={t('trustedRegistry.filters.search')} placeholder={t('trustedRegistry.filters.searchPlaceholder')} value={filters.search} onChange={(event) => filters.setSearch(event.target.value)} className="pr-10" />
      </div>
      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <Select label={t('trustedRegistry.filters.owner')} value={filters.owner} onValueChange={filters.setOwner} options={options(prompts.map((item) => item.ownerName), t('trustedRegistry.filters.allOwners'))} />
        <Select label={t('trustedRegistry.filters.status')} value={filters.status} onValueChange={filters.setStatus} options={['all', 'draft', 'inReview', 'approved', 'inUse', 'retired'].map((value) => ({ value, label: value === 'all' ? t('trustedRegistry.filters.allStatuses') : t(`trustedRegistry.status.${value}`) }))} />
        <Select label={t('trustedRegistry.filters.access')} value={filters.access} onValueChange={filters.setAccess} options={['all', 'private', 'team', 'organization'].map((value) => ({ value, label: t(`trustedRegistry.filters.accessOptions.${value}`) }))} />
      </div>
    </section>
  );
}
