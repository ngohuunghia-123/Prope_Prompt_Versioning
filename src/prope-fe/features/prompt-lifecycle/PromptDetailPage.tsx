import { PencilSimple } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { PromptOverview } from '@/features/prompt-lifecycle/components/PromptOverview';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { promptOptions } from '@/features/prompt-lifecycle/queries';

export function PromptDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { promptId } = useParams();
  const query = useQuery(promptOptions(promptId ?? 'checkout-assistant'));
  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;
  if (!query.data) return <QueryState state="empty" />;
  const prompt = query.data;
  const actionTarget = document.getElementById('topbar-actions');
  return (
    <div className="grid gap-6">
      {actionTarget ? createPortal(<Button type="button" leadingIcon={<PencilSimple aria-hidden className="size-4" />} onClick={() => void navigate(`/app/prompts/${prompt.id}/revisions/new`)}>{t('lifecycle.detail.edit')}</Button>, actionTarget) : null}
      <PromptOverview prompt={prompt} />
    </div>
  );
}
