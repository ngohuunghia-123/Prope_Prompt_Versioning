import { useQuery } from '@tanstack/react-query';
import { useEffect } from 'react';
import { Navigate, useLocation, useParams, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { PromptDetailView } from '@/features/prompt-lifecycle/PromptDetailView';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { getPrompt, getPromptByModelName } from '@/features/prompt-lifecycle/api';
import { promptOverviewUrl } from '@/features/prompt-lifecycle/promptUrls';
import { normalizeOverviewTab, type OverviewTab } from '@/features/prompt-lifecycle/types';
import { trackPromptOpen } from '@/components/promptRecentOpensStorage';

export function PromptDetailPage() {
  const { t } = useTranslation();
  const { promptId, namespace, name } = useParams();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const slugRoute = Boolean(namespace && name);
  const query = useQuery({
    queryKey: ['lifecycle', 'prompt-route', namespace ?? '', name ?? '', promptId ?? ''],
    queryFn: () => slugRoute ? getPromptByModelName(namespace ?? '', name ?? '') : getPrompt(promptId ?? ''),
    enabled: slugRoute || Boolean(promptId),
  });

  useEffect(() => {
    if (query.data) trackPromptOpen(query.data.id, query.data.title);
  }, [query.data]);

  const tab: OverviewTab = normalizeOverviewTab(searchParams.get('tab'));

  if (!promptId && !slugRoute) return <QueryState state="error" titleOverride={t('lifecycle.states.promptNotFound.title')} descriptionOverride={t('lifecycle.states.promptNotFound.description')} />;
  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;
  if (!query.data) return <QueryState state="empty" />;

  if (promptId) return <Navigate replace to={promptOverviewUrl(query.data.modelName, location.search)} />;

  return <PromptDetailView prompt={query.data} tab={tab} />;
}
