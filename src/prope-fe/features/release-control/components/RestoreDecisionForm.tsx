import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowCounterClockwise } from '@phosphor-icons/react';
import { Controller, useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { getRestoreCandidates, restoreDecisionFormSchema, type ReleaseWorkspace, type RestoreDecisionFormValues } from '@/features/release-control/types';

interface RestoreDecisionFormProps { workspace: ReleaseWorkspace; saving: boolean; onSubmit: (values: RestoreDecisionFormValues) => void; }

export function RestoreDecisionForm({ workspace, saving, onSubmit }: RestoreDecisionFormProps) {
  const { t } = useTranslation();
  const candidates = getRestoreCandidates(workspace);
  const { control, register, handleSubmit, formState: { errors } } = useForm<RestoreDecisionFormValues>({ resolver: zodResolver(restoreDecisionFormSchema), defaultValues: { revisionId: candidates[0]?.revisionId ?? '', reason: '' } });
  return <form onSubmit={(event) => void handleSubmit(onSubmit)(event)} className="rounded-panel border border-border bg-surface p-5 shadow-panel sm:p-7"><p className="text-overline font-semibold text-muted">{t('restore.decision.eyebrow')}</p><h2 className="mt-2 text-heading-2 font-semibold">{t('restore.decision.title')}</h2><p className="mt-2 text-body text-muted">{t('restore.decision.description')}</p><div className="mt-5 space-y-4"><Controller name="revisionId" control={control} render={({ field }) => <Select label={t('restore.decision.revision')} name={field.name} value={field.value} onValueChange={field.onChange} error={errors.revisionId ? t('restore.validation.revision') : undefined} options={candidates.map((record) => ({ value: record.revisionId, label: t('revisions.version', { number: record.revisionNumber }) }))} />} /><Textarea className="min-h-28" label={t('restore.decision.reason')} hint={t('restore.decision.reasonHint')} error={errors.reason ? t('restore.validation.reason') : undefined} {...register('reason')} /></div><Button className="mt-5" type="submit" intent="warning" loading={saving} disabled={candidates.length === 0} leadingIcon={<ArrowCounterClockwise aria-hidden className="size-4" />}>{t('restore.actions.reviewRestore')}</Button></form>;
}
