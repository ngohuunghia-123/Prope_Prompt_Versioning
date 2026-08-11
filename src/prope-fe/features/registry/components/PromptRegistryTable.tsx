import { ArrowRight } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { StatusBadge } from '@/components/StatusBadge';
import type { PromptRow, PromptStatus } from '@/features/registry/types';
import { useRegistryFilters } from '@/features/registry/useRegistryFilters';

const statusTone: Record<PromptStatus, 'active' | 'pending' | 'error' | 'disabled'> = {
  draft: 'disabled', inReview: 'pending', approved: 'active', inUse: 'active', retired: 'error',
};

export interface PromptRegistryTableProps { rows: PromptRow[]; }

export function PromptRegistryTable({ rows }: PromptRegistryTableProps) {
  const { t, i18n } = useTranslation();
  const filters = useRegistryFilters(rows);
  const dateFormatter = new Intl.DateTimeFormat(i18n.language, { year: 'numeric', month: 'short', day: 'numeric' });
  return (
    <section className="overflow-hidden rounded-xl border border-border bg-surface shadow-block">
      <div className="flex flex-col gap-4 border-b border-border p-4 sm:p-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-2xl">
          <h2 className="text-heading-2 font-semibold">{t('registry.title')}</h2>
          <p className="mt-1 text-body text-muted">{t('registry.description')}</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:w-160">
          <Input name="registry-search" type="search" label={t('registry.search')} placeholder={t('registry.searchPlaceholder')} value={filters.query} onChange={(event) => filters.setQuery(event.target.value)} />
          <Select name="registry-status" label={t('registry.filter')} value={filters.status} onValueChange={(value) => filters.setStatus(value as PromptStatus | 'all')} options={[{ value: 'all', label: t('registry.all') }, { value: 'draft', label: t('status.draft') }, { value: 'inReview', label: t('status.inReview') }, { value: 'approved', label: t('status.approved') }, { value: 'inUse', label: t('status.inUse') }, { value: 'retired', label: t('status.retired') }]} />
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-240 border-collapse text-left text-body">
          <thead className="bg-subtle text-caption font-medium text-muted">
            <tr>
              <th className="px-6 py-3" scope="col">{t('registry.prompt')}</th>
              <th className="px-6 py-3" scope="col">{t('registry.owner')}</th>
              <th className="px-6 py-3" scope="col">{t('registry.revision')}</th>
              <th className="px-6 py-3" scope="col">{t('registry.status')}</th>
              <th className="px-6 py-3" scope="col">{t('registry.updated')}</th>
              <th className="px-6 py-3 text-right" scope="col">{t('registry.action')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {filters.filteredRows.map((row) => (
              <tr key={row.id} className="h-14 transition-colors hover:bg-subtle/70">
                <th scope="row" className="px-6 py-3.5 font-medium text-ink"><span className="block">{row.name}</span><span className="block text-caption font-normal text-muted">{row.modelName}</span></th>
                <td className="px-6 py-3.5 text-muted">{row.owner}</td>
                <td className="px-6 py-3.5 text-muted">{row.revision}</td>
                <td className="px-6 py-3.5"><StatusBadge tone={statusTone[row.status]}>{t(`status.${row.status}`)}</StatusBadge></td>
                <td className="px-6 py-3.5 whitespace-nowrap text-muted">{dateFormatter.format(new Date(row.updatedAt))}</td>
                <td className="px-6 py-3.5 text-right"><a href={`#prompt-${row.id}`} aria-label={t('registry.openNamed', { name: row.name })} className="inline-grid size-10 place-items-center rounded-lg text-link hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus"><ArrowRight aria-hidden className="size-5" /></a></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {filters.filteredRows.length === 0 ? <p className="p-8 text-center text-body text-muted">{t('registry.empty')}</p> : null}
    </section>
  );
}
