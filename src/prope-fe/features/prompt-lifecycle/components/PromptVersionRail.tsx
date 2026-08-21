import { PencilSimple, Plus, Sparkle, User, X } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Radio } from '@/components/ui/Radio';
import { TagInput } from '@/components/ui/TagInput';
import { Tag } from '@/components/Tag';
import type { Revision } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { cn } from '@/lib/cn';

interface PromptVersionRailProps {
  revisions: Revision[];
  selectedId: string;
  onSelect: (revisionId: string) => void;
  onEditWithAi: () => void;
  onEditManually: () => void;
  onTagsChange: (revisionId: string, tags: string[]) => void;
  savingRevisionId?: string;
}

export function PromptVersionRail({ revisions, selectedId, onSelect, onEditWithAi, onEditManually, onTagsChange, savingRevisionId }: PromptVersionRailProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const [editingTagsFor, setEditingTagsFor] = useState<string>();
  const tagOptions = [...new Set(revisions.flatMap((revision) => revision.tags))].sort((a, b) => a.localeCompare(b));

  return (
    <aside className="flex min-h-full w-full min-w-0 max-w-full flex-col border-b border-border bg-canvas navigation:h-full navigation:min-h-0 navigation:border-r navigation:border-b-0">
      <div className="border-b border-border px-5 py-4">
        <h2 className="!font-sans text-overline font-bold tracking-navigation-overline text-muted uppercase">
          {t('lifecycle.promptDetail.versionTitle')}
        </h2>
      </div>
      <ul className="grid shrink-0 gap-2 border-b border-border p-4 sm:grid-cols-2 navigation:grid-cols-1">
        <li>
          <Button className="w-full max-w-full min-w-0 justify-start rounded-xl p-3 text-left" intent="primary" leadingIcon={<Sparkle aria-hidden className="size-4 shrink-0" weight="fill" />} onClick={onEditWithAi}>
            <span className="min-w-0 truncate">{t('lifecycle.promptDetail.editWithAi')}</span>
          </Button>
        </li>
        <li>
          <Button className="w-full max-w-full min-w-0 justify-start rounded-xl p-3 text-left" intent="secondary" leadingIcon={<PencilSimple aria-hidden className="size-4 shrink-0" />} onClick={onEditManually}>
            <span className="min-w-0 truncate">{t('lifecycle.promptDetail.editManually')}</span>
          </Button>
        </li>
      </ul>
      <ol className="relative isolate grid flex-1 content-start overflow-visible py-1 before:pointer-events-none before:absolute before:top-6 before:bottom-6 before:left-6 before:z-10 before:w-px before:bg-border navigation:min-h-0 navigation:overflow-y-auto">
        {revisions.map((revision) => {
          const selected = revision.id === selectedId;
          const editingTags = editingTagsFor === revision.id;
          return (
            <li key={revision.id} className={cn('relative cursor-pointer border-b border-border transition-colors duration-(--prope-motion-duration-fast)', selected ? 'bg-surface shadow-inset' : 'bg-canvas hover:bg-subtle')}>
              <Radio
                name="prompt-version"
                checked={selected}
                onChange={() => onSelect(revision.id)}
                label={<span className="text-body font-semibold">{t('lifecycle.promptDetail.versionValue', { version: revision.number.replace(/^r/, '') })}</span>}
                description={(
                  <span className="flex min-w-0 items-center gap-1">
                      <span className="shrink-0">{format.date(revision.createdAt)}</span>
                      <span aria-hidden>•</span>
                      <User aria-hidden className="size-3.5 shrink-0 text-muted" />
                      <span className="truncate">{revision.authorEmail ?? revision.author}</span>
                  </span>
                )}
                className={cn(
                  'relative z-20 w-full max-w-full items-start gap-4 border-0 bg-transparent px-4 pt-3 pb-1.5 [&>span:last-child]:min-w-0 [&>span:last-child]:flex-1',
                )}
              />
              <div className="relative z-20 grid min-w-0 gap-2 pr-4 pb-3 pl-16" aria-busy={savingRevisionId === revision.id}>
                {editingTags ? (
                  <div className="grid min-w-0 gap-2">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-caption font-medium text-muted">{t('lifecycle.promptDetail.releaseLabel')}</span>
                      <button type="button" aria-label={t('common.close')} onClick={() => setEditingTagsFor(undefined)} className="grid size-7 shrink-0 place-items-center rounded-md text-muted hover:bg-subtle hover:text-ink focus-visible:outline-2 focus-visible:outline-focus">
                        <X aria-hidden className="size-4" />
                      </button>
                    </div>
                    <TagInput
                      label={t('lifecycle.promptDetail.releaseLabel')}
                      labelHidden
                      placeholder={t('lifecycle.editor.tagsPlaceholder')}
                      createLabel={(tag) => t('lifecycle.editor.createTag', { tag })}
                      removeLabel={(tag) => t('lifecycle.editor.removeTag', { tag })}
                      options={tagOptions}
                      systemTags={['production', 'staging']}
                      values={revision.tags}
                      onChange={(tags) => onTagsChange(revision.id, tags)}
                    />
                  </div>
                ) : (
                  <div className="flex min-w-0 flex-wrap items-center gap-1.5">
                    {revision.tags.map((tag) => <Tag key={tag} state={tag.toLocaleLowerCase() === 'production' || tag.toLocaleLowerCase() === 'staging' ? 'default' : 'neutral'} className="px-2 py-1">{tag}</Tag>)}
                    <button
                      type="button"
                      aria-expanded={false}
                      aria-label={t('lifecycle.promptDetail.releaseLabel')}
                      onClick={() => setEditingTagsFor(revision.id)}
                      className="inline-flex min-h-7 cursor-pointer items-center gap-1 rounded-md border border-dashed border-border px-2 text-caption text-muted hover:bg-subtle hover:text-ink focus-visible:outline-2 focus-visible:outline-focus"
                    >
                      {revision.tags.length === 0 ? <span>{t('lifecycle.promptDetail.releaseLabel')}</span> : null}
                      <Plus aria-hidden className="size-3" />
                    </button>
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </aside>
  );
}
