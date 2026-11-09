import { useQuery } from '@tanstack/react-query';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { getPromptEvalRuns } from '@/features/prompt-lifecycle/insightsApi';
import { ImprovementTrustCard } from '@/features/prompt-lifecycle/components/ImprovementTrustCard';
import { ConnectorError } from '@/features/connectors/ConnectorError';
import { useConnectorImprovement } from '@/features/connectors/useConnectorImprovement';

const evidenceForm = z.object({ run_id: z.string().min(1) });
export function ConnectorImprovement({ promptId, versionId }: { promptId: string; versionId: string }) {
  const { t } = useTranslation(); const improve = useConnectorImprovement(promptId, versionId);
  const evidence = useQuery({ queryKey: ['connector', 'runs', promptId, versionId], queryFn: () => getPromptEvalRuns(promptId, versionId) });
  const form = useForm<z.infer<typeof evidenceForm>>({ resolver: zodResolver(evidenceForm), defaultValues: { run_id: '' } });
  const completed = evidence.data?.filter((run) => run.status === 'completed') ?? [];
  const candidate = improve.run.data?.result_actions.find((action) => action.kind === 'open_improvement' && action.drafted === 'true' && action.candidate_body)?.candidate_body;
  const busy = improve.start.isPending || ['queued', 'running'].includes(improve.run.data?.status ?? '') || improve.history.data?.some((run) => ['queued', 'running'].includes(run.status));
  return <section className="space-y-3">
    <h3 className="font-display text-heading-3">{t('connector.improveTitle')}</h3>
    <p>{t('connector.improveHint')}</p>
    <ConnectorError error={evidence.error ?? improve.history.error ?? improve.run.error ?? improve.start.error ?? improve.review.error} />
    {evidence.isPending || improve.history.isPending || (improve.runId && improve.run.isPending) ? <p role="status">{t('common.loading')}</p> : null}
    {!evidence.isPending && completed.length === 0 ? <p>{t('connector.needEvidence')}</p> : null}
    {improve.history.data?.length === 0 ? <p>{t('connector.noImprovements')}</p> : null}
    <form className="space-y-3" onSubmit={form.handleSubmit((value) => improve.start.mutate(value.run_id))}>
      <Controller control={form.control} name="run_id" render={({ field, fieldState }) => <Select label={t('connector.chooseEvidence')} value={field.value} onValueChange={field.onChange}
        options={[{ value: '', label: t('connector.choose') }, ...completed.map((run) => ({ value: run.run_id, label: t('connector.runOption', { id: run.run_id, status: run.status }) }))]} error={fieldState.error ? t('connector.invalid') : undefined} />} />
      <Button type="submit" loading={Boolean(busy)} disabled={!completed.length || improve.uncertain || improve.history.isPending || improve.history.isError || Boolean(improve.runId && (improve.run.isPending || improve.run.isError))}>{t('connector.startImprovement')}</Button>
    </form>
    {improve.uncertain ? <p role="alert">{t('connector.uncertain')}</p> : null}
    {improve.history.data?.length ? <Select label={t('connector.improvementHistory')} value={improve.runId} onValueChange={improve.setSelected}
      options={improve.history.data.map((run) => ({ value: run.run_id, label: t('connector.runOption', { id: run.run_id, status: run.status }) }))} /> : null}
    {improve.run.data ? <ImprovementTrustCard key={improve.runId} run={improve.run.data} onReview={() => { if (candidate) improve.review.mutate(); }} onRetry={() => form.handleSubmit((value) => { if (!improve.uncertain) improve.start.mutate(value.run_id); })()} /> : null}
    {candidate ? <>
      <Textarea label={t('connector.candidate')} value={candidate} readOnly rows={8} />
      <Button loading={improve.review.isPending} disabled={improve.review.isSuccess} onClick={() => improve.review.mutate()}>{t('connector.reviewCandidate')}</Button>
    </> : null}
    {improve.review.isSuccess ? <p role="status">{t('connector.proposalReady')}</p> : null}
  </section>;
}
