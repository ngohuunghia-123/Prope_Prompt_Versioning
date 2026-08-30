import { CaretDown, Plus } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import type { PromptDraft } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { cn } from '@/lib/cn';

interface DraftPickerMenuProps {
  /** The selected version's drafts — each one is a resumable edit session. */
  drafts: PromptDraft[];
  /** The selected version's number without the `r` prefix, for the labels. */
  versionLabel: string;
  onPickDraft: (draftId: string) => void;
  onCreateDraft: () => void;
  creating?: boolean;
}

/**
 * The edit entry point for a version.
 *
 * Editing never touches the saved version (A-021) — it lands in a draft clone.
 * So "Edit" is a choice, not an action: resume one of the version's existing
 * drafts, or clone a fresh one. The menu closes on pick, on Escape, and on an
 * outside press (the invisible overlay behind the panel).
 */
export function DraftPickerMenu({ drafts, versionLabel, onPickDraft, onCreateDraft, creating }: DraftPickerMenuProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);

  return (
    <div className="relative" onKeyDown={(event) => { if (event.key === 'Escape') close(); }}>
      <Button
        className="w-full max-w-full min-w-0 justify-start rounded-xl p-3 text-left"
        intent="secondary"
        aria-expanded={open}
        aria-haspopup="menu"
        leadingIcon={<CaretDown aria-hidden className="size-4 shrink-0" />}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="min-w-0 truncate">{t('lifecycle.promptDetail.editManually')}</span>
      </Button>
      {open ? (
        <>
          <button type="button" aria-hidden tabIndex={-1} className="fixed inset-0 z-20 cursor-default" onClick={close} />
          <div role="menu" aria-label={t('lifecycle.promptDetail.editManually')} className="absolute inset-x-0 top-full z-30 mt-1 grid content-start gap-0.5 rounded-xl border border-border bg-surface p-1 shadow-floating">
            {drafts.map((draft) => (
              <button
                key={draft.id}
                type="button"
                role="menuitem"
                onClick={() => { close(); onPickDraft(draft.id); }}
                className="flex min-w-0 cursor-pointer flex-col items-start gap-0.5 rounded-lg px-2.5 py-2 text-left hover:bg-subtle focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-focus"
              >
                <span className={cn('w-full truncate text-caption font-semibold text-ink')}>
                  {t('lifecycle.promptDetail.continueDraft', { name: draft.name })}
                </span>
                <span className="text-caption text-muted">{format.date(draft.updatedAt)}</span>
              </button>
            ))}
            <button
              type="button"
              role="menuitem"
              disabled={creating}
              onClick={() => { close(); onCreateDraft(); }}
              className="flex min-w-0 cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-left hover:bg-subtle focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-focus disabled:cursor-wait disabled:opacity-60"
            >
              <Plus aria-hidden className="size-4 shrink-0 text-muted" />
              <span className="truncate text-caption font-semibold text-ink">
                {t('lifecycle.promptDetail.newDraftFrom', { version: versionLabel })}
              </span>
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}
