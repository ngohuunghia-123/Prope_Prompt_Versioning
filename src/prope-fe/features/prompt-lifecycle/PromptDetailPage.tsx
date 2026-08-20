import { useQuery } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useParams, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { PromptDetailView } from '@/features/prompt-lifecycle/PromptDetailView';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { promptOptions } from '@/features/prompt-lifecycle/queries';
import type { OverviewTab } from '@/features/prompt-lifecycle/types';
import { trackPromptOpen } from '@/components/promptRecentOpensStorage';

export function PromptDetailPage() {
  const { t } = useTranslation();
  const { promptId } = useParams();
  const { pathname } = useLocation();
  const resolvedPromptId = promptId ?? '';
  const queryOptions = promptOptions(resolvedPromptId);
  const query = useQuery({
    ...queryOptions,
    enabled: !!promptId,
  });

  useEffect(() => {
    if (query.data) trackPromptOpen(query.data.id, query.data.title);
  }, [query.data]);

  // Derive tab from URL pathname to sync with TopBar tabs
  const tab: OverviewTab = pathname.includes('/improvement')
    ? 'improvement'
    : pathname.includes('/logs')
    ? 'logs'
    : pathname.includes('/production')
      ? 'production'
      : pathname.includes('/evaluation')
        ? 'evaluation'
        : pathname.includes('/release')
          ? 'release'
          : 'versioning';

  if (!promptId) return <QueryState state="error" titleOverride={t('lifecycle.states.promptNotFound.title')} descriptionOverride={t('lifecycle.states.promptNotFound.description')} />;
  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;
  if (!query.data) return <QueryState state="empty" />;

  return <PromptDetailView prompt={query.data} tab={tab} />;
}
