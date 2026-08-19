import { Database, Trash } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Notification } from '@/components/Notification';
import { StatusBadge } from '@/components/StatusBadge';
import { Tag } from '@/components/Tag';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { usePromptIndexing } from '@/features/prompt-lifecycle/components/usePromptIndexing';
import type { PromptDetail } from '@/features/prompt-lifecycle/types';

interface PromptIndexPanelProps {
  prompt: PromptDetail;
}

export function PromptIndexPanel({ prompt }: PromptIndexPanelProps) {
  const { t } = useTranslation();
  const indexing = usePromptIndexing(prompt.id);
  const index = indexing.status.data;
  // Only a prompt with a released ('in use') revision can be indexed for search.
  const canIndex = prompt.status === 'inUse';
  const working = indexing.job.data?.status === 'pending' || indexing.job.data?.status === 'running';

  if (indexing.status.isPending) return <QueryState state="loading" loadingLayout="inline" />;
  if (indexing.status.isError) {
    return <QueryState state="error" onRetry={() => void indexing.status.refetch()} />;
  }

  return (
    <section className="bg-surface p-4 sm:p-6" aria-labelledby="prompt-index-title">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Database aria-hidden className="size-5 text-accent" />
            <h2 id="prompt-index-title" className="text-heading-3 font-semibold text-ink">{t('promptSearch.index.title')}</h2>
          </div>
          <p className="mt-2 max-w-prose text-body text-muted">{t('promptSearch.index.description')}</p>
        </div>
        <StatusBadge tone={index?.is_stale ? 'pending' : index?.is_indexed ? 'active' : 'disabled'}>
          {index?.is_stale ? t('promptSearch.index.stale') : index?.is_indexed ? t('promptSearch.index.indexed') : t('promptSearch.index.notIndexed')}
        </StatusBadge>
      </div>

      {/* The button used to be hidden with no explanation, which read as "this
          feature is broken". Indexing is refused server-side for a prompt with no
          released revision (`prompt has no released revision to index`), so the
          panel says that and points at the tab that fixes it. */}
      {!canIndex ? (
        <Notification className="mt-4" tone="info" title={t('promptSearch.index.needsReleaseTitle')}>
          {t('promptSearch.index.needsReleaseDescription')}
        </Notification>
      ) : null}
      {index?.is_stale ? <Notification className="mt-4" tone="info" title={t('promptSearch.index.staleTitle')}>{t('promptSearch.index.staleDescription')}</Notification> : null}
      {indexing.job.data?.status === 'failed' ? <Notification className="mt-4" tone="error" title={t('promptSearch.index.failed')}>{t('promptSearch.index.failedDescription')}</Notification> : null}
      <div className="mt-5 flex flex-wrap gap-2">
        {canIndex
          ? <Button type="button" loading={working || indexing.preview.isFetching} onClick={() => indexing.setPreviewOpen(true)}>{index?.is_indexed || index?.is_stale ? t('promptSearch.index.reindex') : t('promptSearch.index.action')}</Button>
          : <Link to={`/app/prompts/${prompt.id}/release`} className="inline-flex min-h-10 items-center rounded-control border border-border bg-surface px-4 text-body font-semibold text-ink hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus">{t('promptSearch.index.goToRelease')}</Link>}
        {index?.is_indexed || index?.is_stale ? <Button type="button" intent="danger" leadingIcon={<Trash aria-hidden className="size-4" />} loading={indexing.remove.isPending} onClick={() => indexing.remove.mutate()}>{t('promptSearch.index.remove')}</Button> : null}
      </div>

      <Modal open={indexing.previewOpen} title={t('promptSearch.preview.title')} description={t('promptSearch.preview.description')} confirmLabel={t('promptSearch.preview.confirm')} confirmDisabled={!indexing.preview.data || indexing.start.isPending} confirmLoading={indexing.start.isPending} onClose={() => indexing.setPreviewOpen(false)} onConfirm={() => { if (indexing.preview.data) indexing.start.mutate(); }}>
        {indexing.preview.isPending ? <QueryState state="loading" loadingLayout="inline" /> : null}
        {indexing.preview.isError ? <QueryState state="error" onRetry={() => void indexing.preview.refetch()} /> : null}
        {indexing.preview.data ? <div className="grid gap-4">
          <div className="flex flex-wrap gap-2">{indexing.preview.data.keywords.map((keyword) => <Tag key={keyword} state="neutral">{keyword}</Tag>)}</div>
          {indexing.preview.data.duplicate_warning ? <Notification tone="info" title={t('promptSearch.preview.duplicateTitle')}>{t('promptSearch.preview.duplicateDescription', { title: indexing.preview.data.duplicate_warning.title, similarity: Math.round(indexing.preview.data.duplicate_warning.similarity * 100) })}</Notification> : null}
        </div> : null}
      </Modal>
    </section>
  );
}
