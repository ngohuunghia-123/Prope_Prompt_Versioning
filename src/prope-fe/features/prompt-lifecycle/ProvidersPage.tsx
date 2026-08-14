import { CheckCircle, Key, PlugsConnected } from '@phosphor-icons/react';
import { zodResolver } from '@hookform/resolvers/zod';
import { useQuery } from '@tanstack/react-query';
import { Controller, useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { Notification } from '@/components/Notification';
import { StatusBadge } from '@/components/StatusBadge';
import { Tag } from '@/components/Tag';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { providersOptions, useSaveProviderMutation } from '@/features/prompt-lifecycle/queries';
import { providerFormSchema, type ProviderFormValues } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';

export function ProvidersPage() {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const query = useQuery(providersOptions);
  const mutation = useSaveProviderMutation();
  const form = useForm<ProviderFormValues>({ resolver: zodResolver(providerFormSchema), defaultValues: { provider: 'openai', credential: '', model: 'gpt-5.2' } });
  const providerOptions = [{ value: 'openai', label: 'OpenAI' }, { value: 'anthropic', label: 'Anthropic' }];
  const submit = form.handleSubmit((values) => mutation.mutate(values, { onSuccess: () => form.reset({ ...values, credential: '' }) }));
  return (
    <div className="grid gap-6">
      <PageIntro eyebrow={t('lifecycle.providers.eyebrow')} title={t('lifecycle.providers.title')} description={t('lifecycle.providers.description')} />
      {mutation.isSuccess ? <Notification title={t('lifecycle.providers.successTitle')}>{t('lifecycle.providers.successDescription')}</Notification> : null}
      {mutation.isError ? <Notification tone="error" title={t('lifecycle.states.error.title')}>{t('lifecycle.providers.error')}</Notification> : null}
      {query.isPending ? <QueryState state="loading" /> : null}
      {query.isError ? <QueryState state="error" onRetry={() => void query.refetch()} /> : null}
      {query.isSuccess && query.data.length === 0 ? <QueryState state="empty" /> : null}
      {query.isSuccess && query.data.length > 0 ? <div className="grid gap-4 lg:grid-cols-2">{query.data.map((provider) => <Card key={provider.id} title={provider.name}><div className="mt-2 flex items-center justify-between gap-3"><StatusBadge tone={provider.state === 'connected' ? 'active' : 'pending'}>{t(`lifecycle.providers.state.${provider.state}`)}</StatusBadge><span className="text-caption text-muted">{format.date(provider.updatedAt)}</span></div><div className="mt-4 flex flex-wrap gap-2">{provider.models.map((model) => <Tag key={model} state="neutral">{model}</Tag>)}</div></Card>)}</div> : null}
      <form className="grid gap-5 rounded-modal border border-border bg-surface p-5 shadow-panel sm:p-6" onSubmit={(event) => void submit(event)}>
        <div><h3 className="flex items-center gap-2 font-display text-heading-3 text-ink"><PlugsConnected aria-hidden className="size-5 text-secondary" />{t('lifecycle.providers.configure')}</h3><p className="mt-2 text-body text-muted">{t('lifecycle.providers.securityNote')}</p></div>
        <div className="grid gap-4 sm:grid-cols-3">
          <Controller name="provider" control={form.control} render={({ field }) => <Select label={t('lifecycle.providers.provider')} options={providerOptions} value={field.value} onValueChange={field.onChange} />} />
          <Input label={t('lifecycle.providers.credential')} type="password" autoComplete="off" error={form.formState.errors.credential ? t('lifecycle.validation.required') : undefined} {...form.register('credential')} />
          <Input label={t('lifecycle.providers.model')} error={form.formState.errors.model ? t('lifecycle.validation.required') : undefined} {...form.register('model')} />
        </div>
        <div className="flex items-center justify-between gap-4"><p className="flex items-center gap-2 text-caption text-muted"><Key aria-hidden className="size-4" />{t('lifecycle.providers.neverReturned')}</p><Button type="submit" loading={mutation.isPending} leadingIcon={<CheckCircle aria-hidden className="size-4" />}>{t('lifecycle.providers.save')}</Button></div>
      </form>
    </div>
  );
}
