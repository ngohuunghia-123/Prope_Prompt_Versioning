import { Fire, RocketLaunch, ShieldCheck } from '@phosphor-icons/react';
import { zodResolver } from '@hookform/resolvers/zod';
import { Controller, useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Card } from '@/components/Card';
import { Notification } from '@/components/Notification';
import { Button } from '@/components/ui/Button';
import { Radio } from '@/components/ui/Radio';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { promptOptions, useReleaseMutation } from '@/features/prompt-lifecycle/queries';
import { releaseFormSchema, type ReleaseFormValues } from '@/features/prompt-lifecycle/types';
import { useWorkspaceId } from '@/features/prompt-lifecycle/useWorkspaceId';

export function ReleasePage() {
  const { t } = useTranslation();
  const { promptId, versionId } = useParams();
  const workspaceId = useWorkspaceId();
  const prompt = useQuery({
    ...promptOptions(workspaceId, promptId ?? ''),
    enabled: Boolean(workspaceId && promptId),
  });
  const mutation = useReleaseMutation(workspaceId, promptId ?? '');
  const form = useForm<ReleaseFormValues>({ resolver: zodResolver(releaseFormSchema), defaultValues: { action: 'normal', targetRevision: versionId ?? '', reason: '' } });
  const action = form.watch('action');

  // **Only `Approved` revisions may be released, and that is a database
  // constraint rather than this filter** — the constraint is what makes the rule
  // true. Filtering here is so the form does not offer a choice the server will
  // refuse, which is a worse way to learn the same thing.
  const releasable = (prompt.data?.revisions ?? []).filter(
    (revision) => revision.status === 'approved' || revision.status === 'inUse',
  );
  const targetOptions = releasable.map((revision) => ({
    value: revision.id,
    label:
      revision.id === prompt.data?.releasedVersionId
        ? t('lifecycle.release.currentApproved')
        : t('lifecycle.release.previousApproved', { revision: revision.number }),
  }));

  // The compare-and-set. Sending the pointer this screen was drawn from is what
  // stops two people releasing different revisions at the same moment and one of
  // them winning silently.
  const submit = form.handleSubmit((values) =>
    mutation.mutate({ values, expectedCurrent: prompt.data?.releasedVersionId ?? null }),
  );

  if (!promptId) return <QueryState state="empty" />;
  if (prompt.isPending) return <QueryState state="loading" />;
  if (prompt.isError) return <QueryState state="error" onRetry={() => void prompt.refetch()} />;
  return (
    <form className="grid gap-6" onSubmit={(event) => void submit(event)}>
      <PageIntro eyebrow={t('lifecycle.release.eyebrow')} title={t('lifecycle.release.title')} description={t('lifecycle.release.description')} />
      {mutation.isSuccess ? <Notification title={t('lifecycle.release.successTitle')}>{t('lifecycle.release.successDescription')}</Notification> : null}
      {mutation.isError ? <Notification tone="error" title={t('lifecycle.states.error.title')}>{t('lifecycle.release.error')}</Notification> : null}
      <div className="grid gap-6 xl:grid-cols-3">
        <Card className="gap-5 xl:col-span-2" title={t('lifecycle.release.decision')}>
          <fieldset className="grid gap-3">
            <legend className="mb-2 text-body font-semibold text-ink">{t('lifecycle.release.action')}</legend>
            <Radio label={t('lifecycle.release.normal')} value="normal" {...form.register('action')} />
            <Radio label={t('lifecycle.release.restore')} value="restore" {...form.register('action')} />
            <Radio label={t('lifecycle.release.breakGlass')} value="breakGlass" {...form.register('action')} />
          </fieldset>
          <Controller name="targetRevision" control={form.control} render={({ field }) => <Select label={t('lifecycle.release.target')} options={targetOptions} value={field.value} onValueChange={field.onChange} />} />
          {action === 'breakGlass' ? <Textarea className="min-h-24" label={t('lifecycle.release.reason')} error={form.formState.errors.reason ? t('lifecycle.release.reasonRequired') : undefined} {...form.register('reason')} /> : null}
        </Card>
        <div className="grid content-start gap-6">
          <Card title={t('lifecycle.release.guardrails')}><ul className="mt-2 grid gap-3">{['approved', 'recorded', 'gateway'].map((item) => <li key={item} className="flex gap-2"><ShieldCheck aria-hidden className="mt-0.5 size-5 shrink-0 text-success-strong" /><span>{t(`lifecycle.release.rules.${item}`)}</span></li>)}</ul></Card>
          {action === 'breakGlass' ? <Card title={t('lifecycle.release.emergencyTitle')}><p className="flex gap-2"><Fire aria-hidden className="mt-0.5 size-5 shrink-0 text-warning-strong" />{t('lifecycle.release.emergencyDescription')}</p></Card> : null}
        </div>
      </div>
      <div className="flex justify-end"><Button type="submit" intent={action === 'breakGlass' ? 'warning' : 'secondary'} loading={mutation.isPending} leadingIcon={<RocketLaunch aria-hidden className="size-4" />}>{t(action === 'restore' ? 'lifecycle.release.confirmRestore' : action === 'breakGlass' ? 'lifecycle.release.confirmBreakGlass' : 'lifecycle.release.confirmNormal')}</Button></div>
    </form>
  );
}
