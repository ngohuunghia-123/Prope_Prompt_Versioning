import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { ImportItemTable } from '@/features/prompt-ingestion/ImportItemTable';
import { importBatchOptions, importItemsOptions, useCreateCommitProposal, useDecideCommitProposal, useUpdateImportItem } from '@/features/prompt-ingestion/queries';

export function ImportReviewPage() {
  const { batchId = '' } = useParams();
  const { t } = useTranslation();
  const batch = useQuery(importBatchOptions(batchId));
  const items = useQuery(importItemsOptions(batchId));
  const update = useUpdateImportItem(batchId);
  const propose = useCreateCommitProposal(batchId);
  const decide = useDecideCommitProposal(batchId);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [proposalId, setProposalId] = useState<string>();
  useEffect(() => {
    if (!items.data) return;
    setSelected((current) => current.size ? current : new Set(items.data.items.filter((item) => item.state === 'ready' && item.resolution !== 'skip').map((item) => item.id)));
  }, [items.data]);
  if (batch.isLoading || items.isLoading) return <p className="p-6 text-body text-muted">{t('common.loading')}</p>;
  if (batch.isError || items.isError || !batch.data || !items.data) return <p role="alert" className="p-6 text-body text-danger-text">{t('ingestion.review.failed')}</p>;
  const toggle = (id: string) => setSelected((current) => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  const openProposal = async () => {
    const proposal = await propose.mutateAsync({ reviewVersion: batch.data.review_version, itemIds: [...selected] });
    setProposalId(proposal.id);
  };
  const confirm = async () => {
    if (!proposalId) return;
    await decide.mutateAsync({ proposalId, approve: true });
    setProposalId(undefined);
    setSelected(new Set());
  };
  return (
    <main className="flex flex-col gap-5 p-4 sm:p-6 lg:p-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div><h1 className="text-heading-1 font-semibold text-ink">{t('ingestion.review.title')}</h1><p className="mt-1 text-body text-muted">{t('ingestion.review.summary', { total: batch.data.item_count, ready: batch.data.ready_count, errors: batch.data.error_count })}</p></div>
        <div className="flex gap-2"><Button intent="neutral" onClick={() => items.refetch()}>{t('ingestion.review.refresh')}</Button><Button disabled={batch.data.status !== 'review_ready' || selected.size === 0} loading={propose.isPending} onClick={openProposal}>{t('ingestion.review.commit', { count: selected.size })}</Button></div>
      </header>
      {batch.data.status === 'processing' ? <p className="rounded-control bg-info p-3 text-body text-info-strong">{t('ingestion.review.processing')}</p> : null}
      {(propose.isError || decide.isError || update.isError) ? <p role="alert" className="text-body text-danger-text">{t('ingestion.review.actionFailed')}</p> : null}
      <ImportItemTable items={items.data.items} selected={selected} updating={update.isPending} onToggle={toggle} onResolution={(item, resolution) => {
        if (resolution === 'skip') setSelected((current) => { const next = new Set(current); next.delete(item.id); return next; });
        update.mutate({ itemId: item.id, expectedVersion: item.item_version, resolution, targetPromptId: resolution === 'revise' ? item.target_prompt_id ?? item.semantic_matches[0]?.prompt_id : null });
      }} />
      <Link className="w-fit text-body font-medium text-secondary underline-offset-4 hover:underline" to="/app/prompts">{t('ingestion.review.newBatch')}</Link>
      <Modal open={Boolean(proposalId)} title={t('ingestion.confirm.title')} description={t('ingestion.confirm.description', { count: selected.size })} confirmLabel={t('ingestion.confirm.commit')} confirmLoading={decide.isPending} onClose={() => setProposalId(undefined)} onConfirm={confirm} />
    </main>
  );
}
