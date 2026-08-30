import { Plus } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { DatasetCard } from '@/features/prompt-lifecycle/components/DatasetCard';
import { DatasetControlRail } from '@/features/prompt-lifecycle/components/DatasetControlRail';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { datasetsOptions } from '@/features/prompt-lifecycle/queries';

export function DatasetPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const query = useQuery(datasetsOptions);
  const [search, setSearch] = useState('');
  const [tag, setTag] = useState('all');
  const [linked, setLinked] = useState('all');
  const [sort, setSort] = useState('updated');

  const filtered = useMemo(() => {
    if (!query.data) return undefined;
    const needle = search.trim().toLocaleLowerCase();
    return query.data
      .filter((dataset) => !needle || `${dataset.name} ${dataset.description} ${dataset.tags.join(' ')}`.toLocaleLowerCase().includes(needle))
      .filter((dataset) => tag === 'all' || dataset.tags.includes(tag))
      .filter((dataset) => linked === 'all' || (linked === 'linked' ? dataset.linkedPromptIds.length > 0 : dataset.linkedPromptIds.length === 0))
      .sort((a, b) => sort === 'name' ? a.name.localeCompare(b.name) : sort === 'cases' ? b.testCaseCount - a.testCaseCount : Date.parse(b.updatedAt) - Date.parse(a.updatedAt));
  }, [linked, query.data, search, sort, tag]);

  const stats = useMemo(() => {
    if (!query.data) return { total: 0, testCases: 0, linkedPrompts: 0 };
    return {
      total: query.data.length,
      testCases: query.data.reduce((sum, ds) => sum + ds.testCaseCount, 0),
      linkedPrompts: new Set(query.data.flatMap((ds) => ds.linkedPromptIds)).size,
    };
  }, [query.data]);

  const tags = [...new Set((query.data ?? []).flatMap((dataset) => dataset.tags))].sort();
  const clear = () => { setSearch(''); setTag('all'); setLinked('all'); setSort('updated'); };

  return (
    <div className="grid gap-6">
      <PageIntro
        eyebrow={t('lifecycle.dataset.eyebrow')}
        title={t('lifecycle.dataset.title')}
        description={t('lifecycle.dataset.description')}
        action={
          <Button type="button" leadingIcon={<Plus aria-hidden className="size-4" />} onClick={() => void navigate('/app/datasets/new')}>
            {t('lifecycle.dataset.create')}
          </Button>
        }
      />
      {query.isPending ? <QueryState state="loading" loadingLayout="cards" /> : null}
      {query.isError ? <QueryState state="error" onRetry={() => void query.refetch()} /> : null}
      {query.isSuccess ? (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-border bg-surface p-4 shadow-panel">
              <p className="text-caption text-muted">{t('lifecycle.dataset.stats.total')}</p>
              <p className="mt-1 font-display text-heading-2 text-ink">{stats.total}</p>
            </div>
            <div className="rounded-xl border border-border bg-surface p-4 shadow-panel">
              <p className="text-caption text-muted">{t('lifecycle.dataset.stats.testCases')}</p>
              <p className="mt-1 font-display text-heading-2 text-ink">{stats.testCases}</p>
            </div>
            <div className="rounded-xl border border-border bg-surface p-4 shadow-panel">
              <p className="text-caption text-muted">{t('lifecycle.dataset.stats.linkedPrompts')}</p>
              <p className="mt-1 font-display text-heading-2 text-ink">{stats.linkedPrompts}</p>
            </div>
          </div>
          <DatasetControlRail search={search} tag={tag} linked={linked} sort={sort} tags={tags} count={filtered?.length ?? 0} onSearch={setSearch} onTag={setTag} onLinked={setLinked} onSort={setSort} onClear={clear} />
          {filtered?.length === 0 ? (
            <QueryState
              state="empty"
              titleOverride={query.data.length ? t('lifecycle.dataset.noResultsTitle') : t('lifecycle.dataset.emptyTitle')}
              descriptionOverride={query.data.length ? t('lifecycle.dataset.noResultsBody') : t('lifecycle.dataset.emptyBody')}
            />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {filtered?.map((dataset) => (
                <DatasetCard
                  key={dataset.id}
                  dataset={dataset}
                  onClick={() => void navigate(`/app/datasets/${dataset.id}`)}
                />
              ))}
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
