import { ArrowClockwise } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { PromptRegistryTable } from '@/features/registry/components/PromptRegistryTable';
import { promptListOptions } from '@/features/registry/queries';

export interface RegistryViewProps { reviewOnly?: boolean; }

export function RegistryView({ reviewOnly = false }: RegistryViewProps) {
  const { t } = useTranslation();
  const prompts = useQuery(promptListOptions);
  if (prompts.isPending) return <div className="h-72 animate-pulse rounded-xl bg-subtle motion-reduce:animate-none" aria-label={t('common.loading')} />;
  if (prompts.isError) return <section className="rounded-xl border border-danger-strong bg-danger p-8 text-center"><h2 className="text-heading-3 font-semibold text-danger-text">{t('registry.error')}</h2><Button className="mt-4" intent="neutral" leadingIcon={<ArrowClockwise aria-hidden className="size-4" />} onClick={() => void prompts.refetch()}>{t('registry.retry')}</Button></section>;
  const rows = reviewOnly ? prompts.data.filter((prompt) => prompt.status === 'inReview') : prompts.data;
  if (rows.length === 0) return <section className="rounded-xl border border-border bg-surface p-10 text-center text-muted">{t('registry.empty')}</section>;
  return <PromptRegistryTable rows={rows} />;
}
