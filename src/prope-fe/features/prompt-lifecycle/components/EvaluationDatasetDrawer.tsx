import { Play } from '@phosphor-icons/react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import { Notification } from '@/components/Notification';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { ContentSkeleton } from '@/components/ui/ContentSkeleton';
import { Drawer } from '@/components/ui/Drawer';
import { evaluationIsLive } from '@/features/prompt-lifecycle/evalApi';
import { MAX_ATTACHED_DATASETS } from '@/features/prompt-lifecycle/evalTypes';
import {
  evalAttachmentsOptions,
  evalLibraryOptions,
  promptEvalRunsOptions,
  useReplaceDatasetAttachmentsMutation,
  useStartEvalRunsMutation,
} from '@/features/prompt-lifecycle/queries';

interface EvaluationDatasetDrawerProps {
  open: boolean;
  promptId: string;
  revisionId: string;
  onClose: () => void;
}

export function EvaluationDatasetDrawer({ open, promptId, revisionId, onClose }: EvaluationDatasetDrawerProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const library = useQuery({ ...evalLibraryOptions, enabled: open });
  const attachments = useQuery({ ...evalAttachmentsOptions(promptId), enabled: open });
  const replaceAttachments = useReplaceDatasetAttachmentsMutation(promptId);
  const startRuns = useStartEvalRunsMutation(promptId);
  const attached = useMemo(
    () => new Set((attachments.data ?? []).map((item) => item.dataset_id)),
    [attachments.data],
  );
  const live = evaluationIsLive();

  function toggle(datasetId: string, checked: boolean) {
    const next = checked
      ? [...attached, datasetId]
      : [...attached].filter((id) => id !== datasetId);
    replaceAttachments.mutate(next.slice(0, MAX_ATTACHED_DATASETS));
  }

  function run() {
    startRuns.mutate(revisionId, {
      onSuccess: () => {
        void queryClient.invalidateQueries({ queryKey: promptEvalRunsOptions(promptId, revisionId).queryKey });
        onClose();
      },
    });
  }

  const pending = library.isPending || attachments.isPending;
  const failed = library.isError || attachments.isError;

  return (
    <Drawer open={open} onClose={onClose} side="right" title={t('lifecycle.insights.evaluation.quickRun.title')}>
      <div className="flex h-full min-h-0 flex-col">
        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          <p className="text-body text-muted">{t('lifecycle.insights.evaluation.quickRun.description')}</p>
          {!live ? <Notification tone="info" title={t('lifecycle.evalRun.unavailable')} className="mt-4">{t('lifecycle.evalRun.unavailableHint')}</Notification> : null}
          {replaceAttachments.isError ? <Notification tone="error" title={t('lifecycle.evalRun.attachError')} className="mt-4">{t('lifecycle.evalRun.attachErrorHint')}</Notification> : null}
          {startRuns.isError ? <Notification tone="error" title={t('lifecycle.evalRun.runError')} className="mt-4">{t('lifecycle.evalRun.runErrorHint')}</Notification> : null}
          {pending ? <ContentSkeleton label={t('common.loading')} layout="inline" className="mt-5" /> : null}
          {failed ? <Notification tone="error" title={t('lifecycle.states.error.title')} className="mt-4">{t('lifecycle.states.error.description')}</Notification> : null}
          {!pending && !failed ? (
            <ul className="mt-5 grid gap-2">
              {(library.data ?? []).map((dataset) => {
                const checked = attached.has(dataset.dataset_id);
                const atCapacity = attached.size >= MAX_ATTACHED_DATASETS && !checked;
                return (
                  <li key={dataset.dataset_id} className="rounded-xl border border-border p-3">
                    <Checkbox
                      label={dataset.name}
                      checked={checked}
                      disabled={!live || replaceAttachments.isPending || atCapacity}
                      onChange={(event) => toggle(dataset.dataset_id, event.currentTarget.checked)}
                    />
                    <p className="mt-1 pl-7 text-caption text-muted">{t('lifecycle.evalDatasets.caseCount', { count: dataset.case_count })}</p>
                  </li>
                );
              })}
            </ul>
          ) : null}
        </div>
        <div className="border-t border-border p-4">
          <Button
            type="button"
            className="w-full"
            loading={startRuns.isPending}
            disabled={!live || attached.size === 0 || revisionId === ''}
            leadingIcon={<Play aria-hidden weight="fill" className="size-4" />}
            onClick={run}
          >
            {t('lifecycle.evalRun.run', { count: attached.size })}
          </Button>
        </div>
      </div>
    </Drawer>
  );
}
