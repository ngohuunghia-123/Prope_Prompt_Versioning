import { useQuery } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { PromptDetailView } from '@/features/prompt-lifecycle/PromptDetailView';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { promptOptions } from '@/features/prompt-lifecycle/queries';
import { normalizeOverviewTab, type OverviewTab } from '@/features/prompt-lifecycle/types';
import { trackPromptOpen } from '@/components/promptRecentOpensStorage';

export function PromptDetailPage() {
  const { t } = useTranslation();
  const { promptId } = useParams();
  const [searchParams] = useSearchParams();
  const resolvedPromptId = promptId ?? '';
  const queryOptions = promptOptions(resolvedPromptId);
  const query = useQuery({
    ...queryOptions,
    enabled: !!promptId,
  });

  useEffect(() => {
    if (query.data) trackPromptOpen(query.data.id, query.data.title);
  }, [query.data]);

  const tab: OverviewTab = normalizeOverviewTab(searchParams.get('tab'));

  if (!promptId) return <QueryState state="error" titleOverride={t('lifecycle.states.promptNotFound.title')} descriptionOverride={t('lifecycle.states.promptNotFound.description')} />;
  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;
  if (!query.data) return <QueryState state="empty" />;

  return <PromptDetailView prompt={query.data} tab={tab} />;
}
