import { Check, Folder, MagnifyingGlass, SlidersHorizontal } from '@phosphor-icons/react';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Tag } from '@/components/Tag';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { Select } from '@/components/ui/Select';
import type { Prompt } from '@/features/prompt-lifecycle/types';

type PromptSort = 'updated' | 'name' | 'status';

interface PromptPickerDialogProps {
  open: boolean;
  prompts: Prompt[];
  selectedId: string;
  onClose: () => void;
  onChoose: (promptId: string) => void;
}

export function PromptPickerDialog({ open, prompts, selectedId, onClose, onChoose }: PromptPickerDialogProps) {
  const { t } = useTranslation();
  const [search, setSearch] = useState('');
  const [folder, setFolder] = useState('all');
  const [status, setStatus] = useState('all');
  const [tag, setTag] = useState('all');
  const [sort, setSort] = useState<PromptSort>('updated');
  const folders = useMemo(() => [...new Set(prompts.map((prompt) => prompt.folderId).filter(Boolean))] as string[], [prompts]);
  const tags = useMemo(() => [...new Set(prompts.flatMap((prompt) => prompt.tags))].sort(), [prompts]);
  const statuses = useMemo(() => [...new Set(prompts.map((prompt) => prompt.status))], [prompts]);
  const results = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase();
    return prompts
      .filter((prompt) => !needle || `${prompt.title} ${prompt.modelName} ${prompt.tags.join(' ')}`.toLocaleLowerCase().includes(needle))
      .filter((prompt) => folder === 'all' || prompt.folderId === folder)
      .filter((prompt) => status === 'all' || prompt.status === status)
      .filter((prompt) => tag === 'all' || prompt.tags.includes(tag))
      .sort((a, b) => sort === 'name' ? a.title.localeCompare(b.title) : sort === 'status' ? a.status.localeCompare(b.status) : Date.parse(b.updatedAt) - Date.parse(a.updatedAt));
  }, [folder, prompts, search, sort, status, tag]);
  const clear = () => { setSearch(''); setFolder('all'); setStatus('all'); setTag('all'); setSort('updated'); };

  return (
    <Modal open={open} title={t('lifecycle.playground.picker.title')} description={t('lifecycle.playground.picker.description')} confirmLabel={t('common.close')} showCancel={false} onClose={onClose} onConfirm={onClose} size="wide" icon={<SlidersHorizontal className="size-5" weight="bold" />}>
      <div className="grid gap-4">
        <div className="grid gap-3 rounded-xl border border-border bg-subtle p-4 lg:grid-cols-[minmax(0,2fr)_repeat(4,minmax(0,1fr))_auto]">
          <Input label={t('lifecycle.playground.picker.search')} value={search} onChange={(event) => setSearch(event.currentTarget.value)} leadingIcon={<MagnifyingGlass className="size-4" />} />
          <Select label={t('lifecycle.playground.picker.folder')} value={folder} onValueChange={setFolder} options={[{ value: 'all', label: t('lifecycle.playground.picker.allFolders') }, ...folders.map((value) => ({ value, label: value }))]} />
          <Select label={t('lifecycle.playground.picker.status')} value={status} onValueChange={setStatus} options={[{ value: 'all', label: t('lifecycle.playground.picker.allStatuses') }, ...statuses.map((value) => ({ value, label: t(`lifecycle.status.${value}`) }))]} />
          <Select label={t('lifecycle.playground.picker.tag')} value={tag} onValueChange={setTag} options={[{ value: 'all', label: t('lifecycle.playground.picker.allTags') }, ...tags.map((value) => ({ value, label: value }))]} />
          <Select label={t('lifecycle.playground.picker.sort')} value={sort} onValueChange={(value) => setSort(value as PromptSort)} options={(['updated', 'name', 'status'] as const).map((value) => ({ value, label: t(`lifecycle.playground.picker.sortOptions.${value}`) }))} />
          <Button type="button" intent="ghost" className="self-end whitespace-normal px-2" onClick={clear}>{t('lifecycle.playground.picker.clear')}</Button>
        </div>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <p className="text-caption text-muted">{t('lifecycle.playground.picker.results', { count: results.length })}</p>
        </div>
        {results.length ? <ul className="grid gap-2 sm:grid-cols-2">{results.map((prompt) => (
          <li key={prompt.id}>
            <button type="button" onClick={() => { onChoose(prompt.id); onClose(); }} className="group grid w-full gap-3 rounded-xl border border-border bg-surface p-4 text-left shadow-panel hover:border-focus focus-visible:outline-2 focus-visible:outline-focus">
              <span className="flex min-w-0 items-start justify-between gap-3"><span className="min-w-0"><strong className="block truncate text-body text-ink">{prompt.title}</strong><span className="mt-1 flex items-center gap-1 truncate text-caption text-muted"><Folder className="size-4 shrink-0" />{prompt.folderId ?? t('lifecycle.playground.picker.noFolder')}</span></span>{prompt.id === selectedId ? <Check aria-label={t('lifecycle.playground.picker.selected')} className="size-5 shrink-0 text-secondary" weight="bold" /> : null}</span>
              <span className="flex flex-wrap gap-1.5"><Tag state="neutral">{t(`lifecycle.status.${prompt.status}`)}</Tag>{prompt.tags.slice(0, 2).map((value) => <Tag key={value} state="neutral">{value}</Tag>)}</span>
            </button>
          </li>
        ))}</ul> : <div className="rounded-xl border border-dashed border-border p-8 text-center"><p className="font-semibold text-ink">{t('lifecycle.playground.picker.emptyTitle')}</p><p className="mt-1 text-body text-muted">{t('lifecycle.playground.picker.emptyBody')}</p></div>}
      </div>
    </Modal>
  );
}
