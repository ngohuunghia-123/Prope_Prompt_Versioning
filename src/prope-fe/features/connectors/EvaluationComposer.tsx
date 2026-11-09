import { z } from 'zod';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { evaluationProposalSchema, type Pending } from '@/features/connectors/contracts';
import { getAttachments, getRevisions } from '@/features/connectors/api';
import { callHost } from '@/features/connectors/bridge';
import { ConnectorError } from '@/features/connectors/ConnectorError';

export function EvaluationComposer({ proposal, target, onManageDatasets }: { proposal?: Pending; target?: { prompt_id: string; version_id: string }; onManageDatasets?: () => void }) {
  const { t } = useTranslation();
  const result = z.object({ prompt_id: z.string(), version_id: z.string() }).safeParse(target ?? proposal?.result);
  const promptId = result.success ? result.data.prompt_id : '';
  const revisions = useQuery({ queryKey: ['connector', 'revisions', promptId], queryFn: () => getRevisions(promptId), enabled: Boolean(promptId) });
  const attachments = useQuery({ queryKey: ['connector', 'attachments', promptId], queryFn: () => getAttachments(promptId), enabled: Boolean(promptId) });
  const form = useForm<z.infer<typeof evaluationProposalSchema>>({ resolver: zodResolver(evaluationProposalSchema), defaultValues: { prompt_id: promptId, original_version_id: '', candidate_version_id: result.success ? result.data.version_id : '', dataset_id: '' } });
  const stage = useMutation({ mutationFn: (evaluation: z.infer<typeof evaluationProposalSchema>) => proposal ? callHost('stage_evaluation', { proposal_id: proposal.id, evaluation }) : callHost('stage_comparison', evaluation) });
  const manage = useMutation({ mutationFn: () => callHost('manage', { prompt_id: promptId }) });
  if (!result.success) return null;
  if (revisions.isSuccess && revisions.data.length < 2) return <p role="status">{t('connector.needTwoRevisions')}</p>;
  const revisionOptions = [{ value: '', label: t('connector.choose') }, ...(revisions.data ?? []).map((revision) => ({ value: revision.version_id, label: t('connector.revision', { number: revision.revision_number }) }))];
  return <form className="space-y-3 border-t border-border pt-4" onSubmit={form.handleSubmit((values) => stage.mutate(values))}>
    <h3 className="font-display text-heading-3">{t('connector.evaluateTitle')}</h3>
    {revisions.isPending || attachments.isPending ? <p role="status">{t('common.loading')}</p> : null}
    <ConnectorError error={revisions.error ?? attachments.error ?? stage.error ?? manage.error} />
    {(['original_version_id', 'candidate_version_id'] as const).map((name) => <Controller key={name} control={form.control} name={name} render={({ field, fieldState }) => <Select label={t(`connector.${name}`)} options={revisionOptions} value={field.value} onValueChange={field.onChange} error={fieldState.error ? t('connector.invalid') : undefined} />} />)}
    <Controller control={form.control} name="dataset_id" render={({ field, fieldState }) => <Select label={t('connector.dataset')} value={field.value} onValueChange={field.onChange} error={fieldState.error ? t('connector.invalid') : undefined}
      options={[{ value: '', label: t('connector.choose') }, ...(attachments.data ?? []).filter((item) => item.dataset).map((item) => ({ value: item.dataset_id, label: item.dataset?.name ?? item.dataset_id }))]} />} />
    {attachments.data?.length === 0 ? <p>{t('connector.needDataset')}</p> : null}
    <Button type="button" intent="secondary" onClick={() => onManageDatasets ? onManageDatasets() : manage.mutate()}>{t(onManageDatasets ? 'connector.manageDatasets' : 'connector.manageDataset')}</Button>
    <Button type="submit" loading={stage.isPending} disabled={stage.isSuccess}>{t('connector.stageEvaluation')}</Button>
  </form>;
}
