import { zodResolver } from '@hookform/resolvers/zod';
import { MagnifyingGlass } from '@phosphor-icons/react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { similarCheckFormSchema, type SimilarCheckFormValues } from '@/features/similar-check/types';

interface SimilarCheckFormProps { checking: boolean; onSubmit: (values: SimilarCheckFormValues) => void; }

export function SimilarCheckForm({ checking, onSubmit }: SimilarCheckFormProps) {
  const { t } = useTranslation();
  const { register, handleSubmit, formState: { errors } } = useForm<SimilarCheckFormValues>({ resolver: zodResolver(similarCheckFormSchema), defaultValues: { title: '', content: '' } });
  return <form onSubmit={(event) => void handleSubmit(onSubmit)(event)} className="rounded-panel border border-border bg-surface p-5 shadow-panel sm:p-7"><p className="text-overline font-semibold text-muted">{t('similar.form.eyebrow')}</p><h2 className="mt-2 text-heading-2 font-semibold">{t('similar.form.title')}</h2><p className="mt-2 text-body text-muted">{t('similar.form.description')}</p><div className="mt-5 space-y-4"><Input label={t('similar.form.promptTitle')} placeholder={t('similar.form.promptTitlePlaceholder')} error={errors.title ? t('similar.validation.title') : undefined} {...register('title')} /><Textarea label={t('similar.form.content')} placeholder={t('similar.form.contentPlaceholder')} error={errors.content ? t('similar.validation.content') : undefined} {...register('content')} /></div><Button className="mt-5" type="submit" intent="secondary" loading={checking} leadingIcon={<MagnifyingGlass aria-hidden className="size-4" />}>{t('similar.actions.check')}</Button></form>;
}
