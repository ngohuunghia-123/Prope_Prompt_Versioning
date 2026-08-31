import { Sparkle } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Notification } from '@/components/Notification';
import { ImprovementTrustCard } from '@/features/prompt-lifecycle/components/ImprovementTrustCard';
import { draftIdForRun } from '@/features/prompt-lifecycle/draftApi';
import { useManualImprovementRun } from '@/features/prompt-lifecycle/components/useManualImprovementRun';

interface ManualImprovementControlProps {
  promptId: string;
  selectedVersionId: string;
  selectedLabel: string;
  liveVersionId?: string;
  liveLabel?: string;
  onReview: (findingId: string) => void;
  /** Opens the draft a run created, selected under its version in the rail. */
  onOpenDraft: (versionId: string, draftId: string) => void;
}

export function ManualImprovementControl({ promptId, selectedVersionId, selectedLabel, liveVersionId, liveLabel, onReview, onOpenDraft }: ManualImprovementControlProps) {
  const { t } = useTranslation();
  const [confirming, setConfirming] = useState(false);
  const manual = useManualImprovementRun(promptId);
  // Newest run wins: query.data is newest-first, so the first run that produced
  // a draft is either THIS one or the most recent one that did — the link the
  // card shows must survive a run whose drafts the rails refused.
  const latestDraft = manual.query.data
    ?.map((item) => item.result_actions[0]?.drafted === 'true' && item.version_id ? { versionId: item.version_id, draftId: draftIdForRun(item.run_id) } : undefined)
    .find(Boolean);

  return (
    <>
      <Button className="w-full max-w-full min-w-0 justify-start rounded-xl p-3 text-left" intent="primary" leadingIcon={<Sparkle aria-hidden className="size-4 shrink-0" weight="fill" />} onClick={() => setConfirming(true)}>
        <span className="min-w-0 truncate">{t('lifecycle.promptDetail.editWithAi')}</span>
      </Button>
      {manual.run ? <div className="col-span-full -mx-4 -mb-4"><ImprovementTrustCard run={manual.run} onReview={onReview} onOpenDraft={onOpenDraft} latestDraft={latestDraft} onRetry={() => setConfirming(true)} /></div> : null}
      <Modal
        open={confirming}
        title={t('lifecycle.promptDetail.improvementTrust.confirmTitle')}
        description={t('lifecycle.promptDetail.improvementTrust.confirmDescription')}
        confirmLabel={t('lifecycle.promptDetail.improvementTrust.confirmAction')}
        confirmLoading={manual.start.isPending}
        icon={<Sparkle aria-hidden className="size-5" weight="fill" />}
        onClose={() => setConfirming(false)}
        onConfirm={() => manual.start.mutate({ versionId: selectedVersionId }, { onSuccess: () => setConfirming(false) })}
      >
        <dl className="grid gap-3 rounded-control border border-border bg-canvas p-4 text-body">
          <div><dt className="text-caption text-muted">{t('lifecycle.promptDetail.improvementTrust.target')}</dt><dd className="font-semibold text-ink">{selectedLabel}</dd></div>
          <div><dt className="text-caption text-muted">{t('lifecycle.promptDetail.improvementTrust.productionEvidence')}</dt><dd className="font-semibold text-ink">{liveVersionId ? liveLabel : t('lifecycle.promptDetail.improvementTrust.noLive')}</dd></div>
          <div><dt className="text-caption text-muted">{t('lifecycle.promptDetail.improvementTrust.cost')}</dt><dd className="text-ink">{t('lifecycle.promptDetail.improvementTrust.costHint')}</dd></div>
          <div><dt className="text-caption text-muted">{t('lifecycle.promptDetail.improvementTrust.controlTitle')}</dt><dd className="text-ink">{t('lifecycle.promptDetail.improvementTrust.control')}</dd></div>
        </dl>
        {manual.start.isError ? <Notification tone="error" title={t('lifecycle.promptDetail.improvementTrust.startError')}>{t('lifecycle.promptDetail.improvementTrust.startErrorHint')}</Notification> : null}
      </Modal>
    </>
  );
}
