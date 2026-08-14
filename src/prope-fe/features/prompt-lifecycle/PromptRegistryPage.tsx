import { ArrowRight, MagnifyingGlass, Plus } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Tag } from '@/components/Tag';
import { Button } from '@/components/ui/Button';
import { LifecycleStatus } from '@/features/prompt-lifecycle/components/LifecycleStatus';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { promptsOptions } from '@/features/prompt-lifecycle/queries';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { useDashboardContext } from '@/components/DashboardToolbarContext';

export function PromptRegistryPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const format = useLocaleFormatters();
  const query = useQuery(promptsOptions);
  const { filters } = useDashboardContext();

  const filtered = query.data?.filter((prompt) => {
    const haystack = `${prompt.title} ${prompt.modelName} ${prompt.owner} ${prompt.tags.join(' ')}`.toLowerCase();
    return haystack.includes(filters.search.toLowerCase()) && (filters.status === 'all' || prompt.status === filters.status);
  });

  return (
    <div className="grid gap-6">
      <PageIntro
        eyebrow={t('lifecycle.dashboard.eyebrow')}
        title={t('lifecycle.dashboard.title')}
        description={t('lifecycle.dashboard.description')}
        action={<Button type="button" leadingIcon={<Plus aria-hidden className="size-4" />} onClick={() => void navigate('/app/prompts/new/wizard')}>{t('workspace.create')}</Button>}
      />
      {query.isPending ? <QueryState state="loading" /> : null}
      {query.isError ? <QueryState state="error" onRetry={() => void query.refetch()} /> : null}
      {query.isSuccess && filtered?.length === 0 ? <QueryState state="empty" /> : null}
      {query.isSuccess && filtered && filtered.length > 0 ? (
        <div className="overflow-hidden rounded-modal border border-border bg-surface shadow-panel">
          <div className="overflow-x-auto">
            <table className="w-full min-w-3xl border-collapse text-left text-body">
              <thead className="bg-subtle text-caption text-muted">
                <tr>
                  <th className="px-4 py-3 font-semibold">{t('registry.prompt')}</th>
                  <th className="px-4 py-3 font-semibold">{t('registry.owner')}</th>
                  <th className="px-4 py-3 font-semibold">{t('registry.revision')}</th>
                  <th className="px-4 py-3 font-semibold">{t('registry.status')}</th>
                  <th className="px-4 py-3 font-semibold">{t('registry.updated')}</th>
                  <th className="px-4 py-3 text-right font-semibold">{t('registry.action')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filtered.map((prompt) => (
                  <tr key={prompt.id} className="transition-colors duration-(--prope-motion-duration-fast) hover:bg-subtle/60">
                    <td className="px-4 py-4"><strong className="block text-ink">{prompt.title}</strong><code className="mt-1 block text-caption text-muted">{prompt.modelName}</code><div className="mt-2 flex flex-wrap gap-1.5">{prompt.tags.map((tag) => <Tag key={tag} state="neutral">{tag}</Tag>)}</div></td>
                    <td className="px-4 py-4 text-muted">{prompt.owner}</td>
                    <td className="px-4 py-4 font-medium text-ink">{prompt.revision}</td>
                    <td className="px-4 py-4"><LifecycleStatus status={prompt.status} /></td>
                    <td className="px-4 py-4 text-muted">{format.date(prompt.updatedAt)}</td>
                    <td className="px-4 py-4 text-right"><Button type="button" intent="ghost" trailingIcon={<ArrowRight aria-hidden className="size-4" />} aria-label={t('registry.openNamed', { name: prompt.title })} onClick={() => void navigate(`/app/prompts/${prompt.id}`)}>{t('registry.open')}</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
      <p className="flex items-center gap-2 text-caption text-muted"><MagnifyingGlass aria-hidden className="size-4" />{t('workspace.mockNotice')}</p>
    </div>
  );
}
