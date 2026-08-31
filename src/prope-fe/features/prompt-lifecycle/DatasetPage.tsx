import { Plus } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Notification } from '@/components/Notification';
import { DatasetCard } from '@/features/prompt-lifecycle/components/DatasetCard';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { evaluationIsLive } from '@/features/prompt-lifecycle/evalApi';
import { evalLibraryOptions } from '@/features/prompt-lifecycle/queries';

type DatasetTab = 'all' | string;

/** The dataset library. The same `EvalDataset` rows the evaluation workspace's
 * tree ticks, browsed in full: this page and the tree are two windows on one
 * library, so a set created here is attachable there without a refresh. */
export function DatasetPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const query = useQuery(evalLibraryOptions);
  const [activeTab, setActiveTab] = useState<DatasetTab>('all');

  const filtered = useMemo(() => {
    if (!query.data) return undefined;
    const filteredData = activeTab === 'all'
      ? query.data
      : query.data.filter((dataset) => dataset.tags.includes(activeTab));
    return [...filteredData].sort((a, b) => a.name.localeCompare(b.name));
  }, [query.data, activeTab]);

  const stats = useMemo(() => {
    if (!query.data) return { total: 0, cases: 0, readOnly: 0 };
    return {
      total: query.data.length,
      cases: query.data.reduce((sum, dataset) => sum + dataset.case_count, 0),
      readOnly: query.data.filter((dataset) => dataset.read_only).length,
    };
  }, [query.data]);

  const tabs: { id: DatasetTab; label: string }[] = [
    { id: 'all', label: t('lifecycle.dataset.tabs.all') },
    ...[...new Set((query.data ?? []).flatMap((dataset) => dataset.tags))].sort().map((tag) => ({ id: tag, label: tag })),
  ];

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
      {query.isSuccess && !evaluationIsLive() ? (
        <Notification tone="info" title={t('lifecycle.evalRun.unavailable')}>
          {t('lifecycle.evalRun.unavailableHint')}
        </Notification>
      ) : null}
      {query.isSuccess ? (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-border bg-surface p-4 shadow-panel">
              <p className="text-caption text-muted">{t('lifecycle.dataset.stats.total')}</p>
              <p className="mt-1 font-display text-heading-2 text-ink">{stats.total}</p>
            </div>
            <div className="rounded-xl border border-border bg-surface p-4 shadow-panel">
              <p className="text-caption text-muted">{t('lifecycle.dataset.stats.cases')}</p>
              <p className="mt-1 font-display text-heading-2 text-ink">{stats.cases}</p>
            </div>
            <div className="rounded-xl border border-border bg-surface p-4 shadow-panel">
              <p className="text-caption text-muted">{t('lifecycle.dataset.stats.readOnly')}</p>
              <p className="mt-1 font-display text-heading-2 text-ink">{stats.readOnly}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-1 border-b border-border pb-px">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`rounded-t-lg px-4 py-2 text-body transition-colors duration-(--prope-motion-duration-fast) ${
                  activeTab === tab.id
                    ? 'border border-border border-b-transparent bg-surface font-semibold text-ink'
                    : 'text-muted hover:bg-subtle hover:text-ink'
                }`}
              >
                {tab.label}
                {query.data && tab.id !== 'all' && (
                  <span className="ml-1.5 text-caption">
                    ({query.data.filter((dataset) => dataset.tags.includes(tab.id)).length})
                  </span>
                )}
              </button>
            ))}
          </div>
          {filtered?.length === 0 ? (
            <QueryState
              state="empty"
              titleOverride={t('lifecycle.dataset.empty.title')}
              descriptionOverride={t('lifecycle.dataset.empty.body')}
            />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {filtered?.map((dataset) => (
                <DatasetCard
                  key={dataset.dataset_id}
                  dataset={dataset}
                  onClick={() => void navigate(`/app/datasets/${encodeURIComponent(dataset.dataset_id)}`)}
                />
              ))}
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
