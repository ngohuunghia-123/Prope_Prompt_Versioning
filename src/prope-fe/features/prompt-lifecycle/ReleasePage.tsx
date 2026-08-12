import { ArrowLeft, Fire, RocketLaunch, ShieldCheck } from '@phosphor-icons/react';
import { zodResolver } from '@hookform/resolvers/zod';
import { Controller, useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import { Card } from '@/components/Card';
import { Notification } from '@/components/Notification';
import { Button } from '@/components/ui/Button';
import { Radio } from '@/components/ui/Radio';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { useReleaseMutation } from '@/features/prompt-lifecycle/queries';
import { releaseFormSchema, type ReleaseFormValues } from '@/features/prompt-lifecycle/types';

export function ReleasePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { revisionId } = useParams();
  const mutation = useReleaseMutation();
  const form = useForm<ReleaseFormValues>({ resolver: zodResolver(releaseFormSchema), defaultValues: { action: 'normal', targetRevision: revisionId ?? 'rev_checkout_11', reason: '' } });
  const action = form.watch('action');
  const targetOptions = [
    { value: revisionId ?? 'rev_checkout_11', label: t('lifecycle.release.currentApproved') },
    { value: 'rev_checkout_11', label: t('lifecycle.release.previousApproved', { revision: 'r11' }) },
    { value: 'rev_checkout_10', label: t('lifecycle.release.previousApproved', { revision: 'r10' }) },
  ];
  const submit = form.handleSubmit((values) => mutation.mutate(values));
  return (
    <form className="grid gap-6" onSubmit={(event) => void submit(event)}>
      <Button className="w-fit" type="button" intent="ghost" leadingIcon={<ArrowLeft aria-hidden className="size-4" />} onClick={() => void navigate('/app/prompts/checkout-assistant')}>{t('lifecycle.release.back')}</Button>
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
