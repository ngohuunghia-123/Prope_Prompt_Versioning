import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowCounterClockwise, Check } from '@phosphor-icons/react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { Textarea } from '@/components/ui/Textarea';
import { reviewDecisionFormSchema, type ReviewDecisionFormValues } from '@/features/review/types';

interface ReviewDecisionFormProps { saving: boolean; hasFailures: boolean; onSubmit: (values: ReviewDecisionFormValues) => void; }

export function ReviewDecisionForm({ saving, hasFailures, onSubmit }: ReviewDecisionFormProps) {
  const { t } = useTranslation();
  const { register, handleSubmit, setValue, formState: { errors } } = useForm<ReviewDecisionFormValues>({ resolver: zodResolver(reviewDecisionFormSchema), defaultValues: { decision: 'approved', reason: '', comment: '', diffReviewed: false, evidenceReviewed: false, usageReviewed: false } });
  const submitWith = (decision: ReviewDecisionFormValues['decision']) => {
    setValue('decision', decision);
    void handleSubmit(onSubmit)();
  };
  return <form onSubmit={(event) => event.preventDefault()} className="rounded-panel border border-border bg-surface p-5 shadow-panel sm:p-7"><p className="text-overline font-semibold text-muted">{t('review.decision.eyebrow')}</p><h2 className="mt-2 text-heading-2 font-semibold">{t('review.decision.title')}</h2><p className="mt-2 text-body text-muted">{t(hasFailures ? 'review.decision.failureDescription' : 'review.decision.description')}</p><fieldset className="mt-5 space-y-3 rounded-modal border border-border bg-canvas p-4"><legend className="px-1 text-body font-semibold text-ink">{t('review.checklist.legend')}</legend><Checkbox label={t('review.checklist.diff')} {...register('diffReviewed')} /><Checkbox label={t('review.checklist.evidence')} {...register('evidenceReviewed')} /><Checkbox label={t('review.checklist.usage')} {...register('usageReviewed')} />{errors.diffReviewed || errors.evidenceReviewed || errors.usageReviewed ? <p role="alert" className="text-caption text-danger-text">{t('review.validation.checklist')}</p> : null}</fieldset><div className="mt-5 grid gap-4 lg:grid-cols-2"><Textarea className="min-h-28" label={t('review.decision.reason')} hint={t('review.decision.reasonHint')} error={errors.reason ? t('review.validation.reason') : undefined} {...register('reason')} /><Textarea className="min-h-28" label={t('review.decision.comment')} hint={t('review.decision.commentHint')} {...register('comment')} /></div><div className="mt-5 flex flex-wrap gap-2"><Button type="button" intent="success" loading={saving} leadingIcon={<Check aria-hidden className="size-4" />} onClick={() => submitWith('approved')}>{t('review.actions.approve')}</Button><Button type="button" intent="neutral" disabled={saving} leadingIcon={<ArrowCounterClockwise aria-hidden className="size-4" />} onClick={() => submitWith('changesRequested')}>{t('review.actions.requestChanges')}</Button></div></form>;
}
