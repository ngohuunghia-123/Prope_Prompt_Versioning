import { ArrowLeft, PencilSimple } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { EvaluationWorkflow } from '@/features/prompt-lifecycle/components/EvaluationWorkflow';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
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
  return (
    <div className="grid gap-6">
      <Button className="w-fit" type="button" intent="ghost" leadingIcon={<ArrowLeft aria-hidden className="size-4" />} onClick={() => void navigate('/app/prompts')}>{t('workspace.backToPrompts')}</Button>
      <PageIntro eyebrow={prompt.modelName} title={prompt.title} description={prompt.purpose} action={<Button type="button" leadingIcon={<PencilSimple aria-hidden className="size-4" />} onClick={() => void navigate(`/app/prompts/${prompt.id}/revisions/new`)}>{t('lifecycle.detail.edit')}</Button>} />
      <EvaluationWorkflow promptId={prompt.id} />
    </div>
  );
}
