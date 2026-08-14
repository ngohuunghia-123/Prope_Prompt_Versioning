import { Database, Plus } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { datasetsOptions } from '@/features/prompt-lifecycle/queries';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import type { Dataset, DatasetType } from '@/features/prompt-lifecycle/types';

type DatasetTab = 'all' | DatasetType;

const datasetTypeOrder: Record<DatasetType, number> = {
  golden: 0,
  regression: 1,
  'red-team': 2,
};

function DatasetTypeBadge({ type }: { type: DatasetType }) {
  const { t } = useTranslation();
  const styles: Record<DatasetType, string> = {
    golden: 'bg-success/15 text-success border-success/30',
    regression: 'bg-warning/15 text-warning border-warning/30',
    'red-team': 'bg-danger/15 text-danger border-danger/30',
  };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-caption font-medium ${styles[type]}`}>
      {type === 'golden' && <Database aria-hidden className="size-3" weight="bold" />}
      {t(`lifecycle.dataset.types.${type === 'red-team' ? 'redTeam' : type}`)}
    </span>
  );
}

function DatasetCard({ dataset, onClick }: { dataset: Dataset; onClick: () => void }) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  return (
    <button
      type="button"
      onClick={onClick}
      className="group w-full text-left rounded-xl border border-border bg-surface p-4 shadow-panel transition-all duration-(--prope-motion-duration-fast) hover:border-focus hover:shadow-elevated focus-visible:outline-2 focus-visible:outline-focus"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="grid min-w-0 flex-1 gap-2">
          <h3 className="truncate text-body font-semibold text-ink group-hover:text-link">{dataset.name}</h3>
          <p className="line-clamp-2 text-caption text-muted">{dataset.description}</p>
        </div>
        <DatasetTypeBadge type={dataset.type} />
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border/60 pt-3 text-caption text-muted">
        <div className="flex items-center gap-3">
          <span>{t('lifecycle.dataset.fields.testCases')}: <strong className="text-ink">{dataset.testCaseCount}</strong></span>
          <span>{t('lifecycle.dataset.fields.prompts')}: <strong className="text-ink">{dataset.linkedPromptIds.length}</strong></span>
        </div>
        <span>{format.date(dataset.updatedAt)}</span>
      </div>
    </button>
  );
}

export function DatasetPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const query = useQuery(datasetsOptions);
  const [activeTab, setActiveTab] = useState<DatasetTab>('all');

  const filtered = useMemo(() => {
    if (!query.data) return undefined;
    const filteredData = activeTab === 'all'
      ? query.data
      : query.data.filter((ds) => ds.type === activeTab);
    return [...filteredData].sort((a, b) => {
      const typeDiff = datasetTypeOrder[a.type] - datasetTypeOrder[b.type];
      if (typeDiff !== 0) return typeDiff;
      return a.name.localeCompare(b.name);
    });
  }, [query.data, activeTab]);

  const stats = useMemo(() => {
    if (!query.data) return { total: 0, testCases: 0, linkedPrompts: 0 };
    return {
      total: query.data.length,
      testCases: query.data.reduce((sum, ds) => sum + ds.testCaseCount, 0),
      linkedPrompts: new Set(query.data.flatMap((ds) => ds.linkedPromptIds)).size,
    };
  }, [query.data]);

  const tabs: { id: DatasetTab; label: string }[] = [
    { id: 'all', label: t('lifecycle.dataset.tabs.all') },
    { id: 'golden', label: t('lifecycle.dataset.tabs.golden') },
    { id: 'regression', label: t('lifecycle.dataset.tabs.regression') },
    { id: 'red-team', label: t('lifecycle.dataset.tabs.redTeam') },
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
      {query.isPending ? <QueryState state="loading" /> : null}
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
                    ({query.data.filter((ds) => ds.type === tab.id).length})
                  </span>
                )}
              </button>
            ))}
          </div>
          {filtered?.length === 0 ? (
            <QueryState
              state="empty"
              titleOverride={t('lifecycle.dataset.emptyTitle')}
              descriptionOverride={t('lifecycle.dataset.emptyBody')}
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
