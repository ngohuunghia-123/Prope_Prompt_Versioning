import { CaretDown, Plus, User, X } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Radio } from '@/components/ui/Radio';
import { TagInput } from '@/components/ui/TagInput';
import { Tag } from '@/components/Tag';
import type { PromptDraft, Revision } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { useWorkspaceDisplayNames } from '@/features/prompt-lifecycle/useWorkspaceDisplayNames';
import { ManualImprovementControl } from '@/features/prompt-lifecycle/components/ManualImprovementControl';
import { DraftPickerMenu } from '@/features/prompt-lifecycle/components/DraftPickerMenu';
import { VersionRailDraftList } from '@/features/prompt-lifecycle/components/VersionRailDraftList';
import { cn } from '@/lib/cn';

interface PromptVersionRailProps {
  revisions: Revision[];
  drafts: PromptDraft[];
  selectedId: string;
  selectedDraftId?: string;
  onSelect: (revisionId: string) => void;
  onSelectDraft: (draftId: string) => void;
  onRenameDraft: (draftId: string, name: string) => void;
  onPromoteDraft: (draftId: string) => void;
  /** The publish gate (requirement 1): no new version until the newest one is published. */
  canPromote: boolean;
  promoteBlockedReason: string;
  promotingDraftId?: string;
  creatingDraft?: boolean;
  onPickDraft: (draftId: string) => void;
  onCreateDraft: () => void;
  onTagsChange: (revisionId: string, tags: string[]) => void;
  savingRevisionId?: string;
  promptId: string;
  liveVersionId?: string;
  onReviewImprovement: (findingId: string) => void;
}

export function PromptVersionRail({ revisions, drafts, selectedId, selectedDraftId, onSelect, onSelectDraft, onRenameDraft, onPromoteDraft, canPromote, promoteBlockedReason, promotingDraftId, creatingDraft, onPickDraft, onCreateDraft, onTagsChange, savingRevisionId, promptId, liveVersionId, onReviewImprovement }: PromptVersionRailProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const { userName } = useWorkspaceDisplayNames();
  const [editingTagsFor, setEditingTagsFor] = useState<string>();
  const tagOptions = [...new Set(revisions.flatMap((revision) => revision.tags))].sort((a, b) => a.localeCompare(b));
  const selectedRevision = revisions.find((revision) => revision.id === selectedId);
  // Selecting a version IS expanding it: its drafts are the rows revealed
  // beneath, and every other version stays collapsed.
  const selectedDrafts = selectedRevision ? drafts.filter((draft) => draft.parentRevisionId === selectedRevision.id) : [];

  return (
    <aside className="flex min-h-full w-full min-w-0 max-w-full flex-col border-b border-border bg-canvas navigation:h-full navigation:min-h-0 navigation:overflow-y-auto navigation:border-r navigation:border-b-0">
      <div className="border-b border-border px-5 py-4">
        <h2 className="!font-sans text-overline font-bold tracking-navigation-overline text-muted uppercase">
          {t('lifecycle.promptDetail.versionTitle')}
        </h2>
      </div>
      <div className="grid shrink-0 gap-2 border-b border-border p-4 sm:grid-cols-2 navigation:grid-cols-1">
        <div>
          <DraftPickerMenu
            drafts={selectedDrafts}
            versionLabel={selectedRevision?.number.replace(/^r/, '') ?? ''}
            onPickDraft={onPickDraft}
            onCreateDraft={onCreateDraft}
            creating={creatingDraft}
          />
        </div>
        <ManualImprovementControl
          promptId={promptId}
          selectedVersionId={selectedId}
          selectedLabel={revisions.find((item) => item.id === selectedId)?.number ?? selectedId}
          liveVersionId={liveVersionId}
          liveLabel={revisions.find((item) => item.id === liveVersionId)?.number}
          onReview={onReviewImprovement}
          // The run's draft is a registry revision like any other: "review the
          // draft" is just selecting it in the tree below.
          onOpenDraft={onSelect}
        />
      </div>
      <ol className="grid flex-1 content-start py-1 navigation:min-h-0 navigation:overflow-y-auto">
        {revisions.map((revision) => {
          const selected = revision.id === selectedId;
          const editingTags = editingTagsFor === revision.id;
          const versionDrafts = drafts.filter((draft) => draft.parentRevisionId === revision.id);
          return (
            <li key={revision.id} className={cn('cursor-pointer border-b border-border transition-colors duration-(--prope-motion-duration-fast)', selected ? 'bg-surface shadow-inset' : 'bg-canvas hover:bg-subtle')}>
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
                      <span className="truncate">{userName(revision.author)}</span>
                  </span>
                )}
                className={cn(
                  'w-full max-w-full items-start gap-4 border-0 bg-transparent px-4 pt-3 pb-1.5 [&>span:last-child]:min-w-0 [&>span:last-child]:flex-1',
                )}
              />
              <div className="grid min-w-0 gap-2 pr-4 pb-3 pl-16" aria-busy={savingRevisionId === revision.id}>
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
                      menuLayout="inline"
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
                {selected && versionDrafts.length > 0 ? (
                  <div className="-ml-6 min-w-0 border-l border-border pl-3">
                    <VersionRailDraftList
                      drafts={versionDrafts}
                      selectedDraftId={selectedDraftId}
                      onSelectDraft={onSelectDraft}
                      onRenameDraft={onRenameDraft}
                      onPromoteDraft={onPromoteDraft}
                      canPromote={canPromote}
                      promoteBlockedReason={promoteBlockedReason}
                      promotingDraftId={promotingDraftId}
                    />
                  </div>
                ) : null}
                {!selected && versionDrafts.length > 0 ? (
                  <div className="flex items-center gap-1 text-caption text-muted">
                    <CaretDown aria-hidden className="size-3" />
                    {t('lifecycle.promptDetail.draftsCount', { count: versionDrafts.length })}
                  </div>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
    </aside>
  );
}
