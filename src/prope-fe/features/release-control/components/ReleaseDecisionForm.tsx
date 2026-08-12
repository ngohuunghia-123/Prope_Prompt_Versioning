import { zodResolver } from '@hookform/resolvers/zod';
import { RocketLaunch } from '@phosphor-icons/react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { Textarea } from '@/components/ui/Textarea';
import { releaseDecisionFormSchema, type ReleaseDecisionFormValues } from '@/features/release-control/types';

interface ReleaseDecisionFormProps { saving: boolean; disabled: boolean; onSubmit: (values: ReleaseDecisionFormValues) => void; }

export function ReleaseDecisionForm({ saving, disabled, onSubmit }: ReleaseDecisionFormProps) {
  const { t } = useTranslation();
  const { register, handleSubmit, watch, formState: { errors } } = useForm<ReleaseDecisionFormValues>({ resolver: zodResolver(releaseDecisionFormSchema), defaultValues: { reason: '', breakGlass: false } });
  const breakGlass = watch('breakGlass');
  return <form onSubmit={(event) => void handleSubmit(onSubmit)(event)} className="rounded-panel border border-border bg-surface p-5 shadow-panel sm:p-7"><p className="text-overline font-semibold text-muted">{t('release.decision.eyebrow')}</p><h2 className="mt-2 text-heading-2 font-semibold">{t('release.decision.title')}</h2><p className="mt-2 text-body text-muted">{t('release.decision.description')}</p><div className="mt-5 rounded-modal border border-warning-strong bg-warning p-4"><Checkbox label={t('release.decision.breakGlass')} {...register('breakGlass')} /><p className="mt-2 text-caption text-warning-strong">{t('release.decision.breakGlassHint')}</p></div><Textarea className="mt-5 min-h-28" label={breakGlass ? t('release.decision.breakGlassReason') : t('release.decision.reason')} hint={t('release.decision.reasonHint')} error={errors.reason ? t('release.validation.reason') : undefined} {...register('reason')} /><Button className="mt-5" type="submit" intent={breakGlass ? 'warning' : 'success'} loading={saving} disabled={disabled && !breakGlass} leadingIcon={<RocketLaunch aria-hidden className="size-4" weight="fill" />}>{breakGlass ? t('release.actions.breakGlass') : t('release.actions.release')}</Button></form>;
}
