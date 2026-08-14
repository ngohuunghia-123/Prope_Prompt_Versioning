import { PencilSimple } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { PromptOverview } from '@/features/prompt-lifecycle/components/PromptOverview';
import { PromptIndexPanel } from '@/features/prompt-lifecycle/components/PromptIndexPanel';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { promptOptions } from '@/features/prompt-lifecycle/queries';
import { useWorkspaceId } from '@/features/prompt-lifecycle/useWorkspaceId';

export function PromptDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { promptId } = useParams();
  const workspaceId = useWorkspaceId();
  // Held until both are known. `enabled` rather than a placeholder id: a request
  // for a prompt nobody named would answer not-found, and a not-found is what the
  // API says about a prompt this actor may not see — so a speculative request
  // would render "no such prompt" for a routing gap.
  const query = useQuery({ ...promptOptions(workspaceId, promptId ?? ''), enabled: Boolean(workspaceId && promptId) });
  if (!promptId) return <QueryState state="empty" />;
  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;
  if (!query.data) return <QueryState state="empty" />;
  const prompt = query.data;
  const actionTarget = document.getElementById('topbar-actions');
  return (
    <div className="grid gap-6">
      {actionTarget ? createPortal(<Button type="button" leadingIcon={<PencilSimple aria-hidden className="size-4" />} onClick={() => void navigate(`/app/prompts/${prompt.id}/revisions/new`)}>{t('lifecycle.detail.edit')}</Button>, actionTarget) : null}
      <PromptOverview prompt={prompt} />
      <PromptIndexPanel prompt={prompt} workspaceId={workspaceId} />
    </div>
  );
}
