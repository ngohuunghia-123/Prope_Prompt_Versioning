import { ArrowRight, MagnifyingGlass, Plus, Sparkle } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useDeferredValue, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Tag } from '@/components/Tag';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { LifecycleStatus } from '@/features/prompt-lifecycle/components/LifecycleStatus';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { PromptSearchResults } from '@/features/prompt-lifecycle/components/PromptSearchResults';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { promptSearchOptions, promptsOptions } from '@/features/prompt-lifecycle/queries';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { useWorkspaceId } from '@/features/prompt-lifecycle/useWorkspaceId';

export function PromptRegistryPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const format = useLocaleFormatters();
  const workspaceId = useWorkspaceId();
  const query = useQuery({ ...promptsOptions(workspaceId), enabled: Boolean(workspaceId) });
  const [search, setSearch] = useState('');
  const deferredSearch = useDeferredValue(search.trim());
  const [searchMode, setSearchMode] = useState<'quick' | 'ai'>('quick');
  const searchQuery = useQuery({
    ...promptSearchOptions(workspaceId, deferredSearch, searchMode),
    enabled: Boolean(workspaceId && deferredSearch),
  });
  const [status, setStatus] = useState('all');
  const filtered = query.data?.filter((prompt) => {
    return status === 'all' || prompt.status === status;
  });
  const statusOptions = [
    { value: 'all', label: t('registry.all') },
    { value: 'draft', label: t('status.draft') },
    { value: 'inReview', label: t('status.inReview') },
    { value: 'approved', label: t('status.approved') },
    { value: 'inUse', label: t('status.inUse') },
  ];

  return (
    <div className="grid gap-6">
      <PageIntro
        eyebrow={t('lifecycle.registry.eyebrow')}
        title={t('lifecycle.registry.title')}
        description={t('lifecycle.registry.description')}
        action={<Button type="button" leadingIcon={<Plus aria-hidden className="size-4" />} onClick={() => void navigate('/app/prompts/new')}>{t('workspace.create')}</Button>}
      />
      <div className="grid gap-3 rounded-xl border border-border bg-surface p-4 shadow-panel sm:grid-cols-[minmax(0,1fr)_auto_auto]">
        <Input label={t('registry.search')} labelHidden value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t('registry.searchPlaceholder')} type="search" name="prompt-search" />
        {deferredSearch ? <Button type="button" intent={searchMode === 'ai' ? 'primary' : 'neutral'} leadingIcon={<Sparkle aria-hidden className="size-4" />} onClick={() => setSearchMode((current) => current === 'quick' ? 'ai' : 'quick')}>{searchMode === 'quick' ? t('promptSearch.searchWithAi') : t('promptSearch.useQuick')}</Button> : null}
        {!deferredSearch ? <Select label={t('registry.filter')} options={statusOptions} value={status} onValueChange={setStatus} /> : null}
      </div>
      {deferredSearch ? <PromptSearchResults results={searchQuery.data?.prompts} pending={searchQuery.isPending} error={searchQuery.isError} mode={searchMode} onRetry={() => void searchQuery.refetch()} onOpen={(id) => void navigate(`/app/prompts/${id}`)} /> : null}
      {!deferredSearch && query.isPending ? <QueryState state="loading" /> : null}
      {!deferredSearch && query.isError ? <QueryState state="error" onRetry={() => void query.refetch()} /> : null}
      {!deferredSearch && query.isSuccess && filtered?.length === 0 ? <QueryState state="empty" /> : null}
      {!deferredSearch && query.isSuccess && filtered && filtered.length > 0 ? (
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
                    {/* Empty until the detail page loads the chain: the list
                        endpoint carries a released *version id* and no revision
                        numbers, and one revisions request per row is a fan-out on
                        the screen most likely to be open. */}
                    <td className="px-4 py-4 font-medium text-ink">{prompt.revision || '—'}</td>
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
      <p className="flex items-center gap-2 text-caption text-muted"><MagnifyingGlass aria-hidden className="size-4" />{t('registry.searchScope')}</p>
    </div>
  );
}
