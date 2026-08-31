import { PencilSimple, RocketLaunch } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Tooltip } from '@/components/ui/Tooltip';
import { Tag } from '@/components/Tag';
import type { PromptDraft } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { cn } from '@/lib/cn';

interface VersionRailDraftListProps {
  drafts: PromptDraft[];
  selectedDraftId?: string;
  onSelectDraft: (draftId: string) => void;
  onRenameDraft: (draftId: string, name: string) => void;
  onPromoteDraft: (draftId: string) => void;
  /** The publish gate (requirement 1): promotion is only offered while the
   * prompt's newest version is the published one. */
  canPromote: boolean;
  promoteBlockedReason: string;
  promotingDraftId?: string;
}

/** The draft rows shown when a version is expanded in the tree. Each draft can
 * be selected (opens its content), renamed inline, and promoted into the
 * prompt's next version. */
export function VersionRailDraftList({ drafts, selectedDraftId, onSelectDraft, onRenameDraft, onPromoteDraft, canPromote, promoteBlockedReason, promotingDraftId }: VersionRailDraftListProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const [renamingId, setRenamingId] = useState<string>();
  const [renameValue, setRenameValue] = useState('');

  const startRename = (draft: PromptDraft) => {
    setRenamingId(draft.id);
    setRenameValue(draft.name);
  };
  const commitRename = () => {
    const draftId = renamingId;
    setRenamingId(undefined);
    const name = renameValue.trim();
    if (!draftId || !name) return;
    onRenameDraft(draftId, name);
  };

  if (drafts.length === 0) return null;

  return (
    <ol aria-label={t('lifecycle.promptDetail.draftsCount', { count: drafts.length })} className="grid content-start gap-0.5 pb-2">
      {drafts.map((draft) => {
        const selected = draft.id === selectedDraftId;
        const renaming = renamingId === draft.id;
        return (
          <li key={draft.id} className="min-w-0 pr-1">
            {renaming ? (
              <div className="px-1 py-0.5">
                <Input
                  label={t('lifecycle.promptDetail.draftNameLabel')}
                  labelHidden
                  value={renameValue}
                  autoFocus
                  className="h-8 py-1 text-caption"
                  onChange={(event) => setRenameValue(event.target.value)}
                  onBlur={commitRename}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') commitRename();
                    if (event.key === 'Escape') setRenamingId(undefined);
                  }}
                />
              </div>
            ) : (
              <div className={cn('flex min-w-0 items-center gap-1.5 rounded-lg px-2 py-1.5 transition-colors duration-(--prope-motion-duration-fast)', selected ? 'bg-subtle' : 'hover:bg-subtle/60')}>
                <button
                  type="button"
                  aria-current={selected || undefined}
                  onClick={() => onSelectDraft(draft.id)}
                  className="flex min-w-0 flex-1 cursor-pointer flex-col items-start gap-0.5 rounded-sm text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                >
                  <span className="flex min-w-0 items-center gap-1.5">
                    <span className="truncate text-caption font-semibold text-ink">{draft.name}</span>
                    <Tag state="neutral" className="px-1.5 py-0.5 text-caption">{t('lifecycle.promptDetail.draftBadge')}</Tag>
                  </span>
                  <span className="text-caption text-muted">{format.date(draft.updatedAt)}</span>
                </button>
                <Tooltip label={t('lifecycle.promptDetail.renameDraft')}>
                  <button
                    type="button"
                    aria-label={t('lifecycle.promptDetail.renameDraft')}
                    onClick={() => startRename(draft)}
                    className="grid size-7 shrink-0 cursor-pointer place-items-center rounded-md text-muted hover:bg-surface hover:text-ink focus-visible:outline-2 focus-visible:outline-focus"
                  >
                    <PencilSimple aria-hidden className="size-3.5" />
                  </button>
                </Tooltip>
                <Tooltip label={canPromote ? t('lifecycle.promptDetail.promoteDraftShort') : promoteBlockedReason}>
                  <Button
                    type="button"
                    size="small"
                    intent="neutral"
                    className="shrink-0"
                    disabled={!canPromote}
                    loading={promotingDraftId === draft.id}
                    leadingIcon={<RocketLaunch aria-hidden className="size-3.5 shrink-0" />}
                    onClick={() => onPromoteDraft(draft.id)}
                  >
                    {t('lifecycle.promptDetail.promoteDraftShort')}
                  </Button>
                </Tooltip>
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
