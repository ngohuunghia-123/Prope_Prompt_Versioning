import { Archive, DotsThree, Eye, PencilSimple } from '@phosphor-icons/react';
import { useState, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Modal } from '@/components/ui/Modal';
import { useRetirePromptMutation } from '@/features/prompt-lifecycle/queries';
import type { Prompt } from '@/features/prompt-lifecycle/types';

interface PromptActionsMenuProps {
  folderId: string;
  prompt: Prompt;
}

export function PromptActionsMenu({ folderId, prompt }: PromptActionsMenuProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const retireMutation = useRetirePromptMutation(folderId);
  const [open, setOpen] = useState(false);
  const [confirmingRetire, setConfirmingRetire] = useState(false);
  const retireBlocked = prompt.status === 'inUse' || prompt.status === 'retired';

  const navigateTo = (path: string) => {
    setOpen(false);
    void navigate(path, { state: { promptTitle: prompt.title } });
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') setOpen(false);
  };

  return (
    <div
      className="relative"
      onClick={(event) => event.stopPropagation()}
      onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false); }}
      onKeyDown={handleKeyDown}
    >
      <button
        type="button"
        aria-label={t('lifecycle.folders.detail.action.menu')}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className="inline-flex size-8 items-center justify-center rounded-lg text-muted transition-colors hover:bg-subtle hover:text-ink focus-visible:outline-2 focus-visible:outline-focus"
      >
        <DotsThree aria-hidden weight="bold" className="size-5" />
      </button>

      {open ? (
        <div role="menu" className="absolute right-0 top-9 z-30 grid min-w-48 gap-1 rounded-lg border border-border bg-surface p-1 shadow-floating">
          <button type="button" role="menuitem" onClick={() => navigateTo(`/app/prompts/${prompt.id}`)} className="flex items-center gap-2 rounded-control px-3 py-2 text-left text-body text-ink hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus">
            <Eye aria-hidden className="size-4" />
            {t('lifecycle.folders.detail.action.open')}
          </button>
          <button type="button" role="menuitem" onClick={() => navigateTo(`/app/prompts/${prompt.id}/edit`)} className="flex items-center gap-2 rounded-control px-3 py-2 text-left text-body text-ink hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus">
            <PencilSimple aria-hidden className="size-4" />
            {t('lifecycle.folders.detail.action.edit')}
          </button>
          <button
            type="button"
            role="menuitem"
            disabled={retireBlocked}
            title={retireBlocked ? t('lifecycle.folders.detail.action.retireBlocked') : undefined}
            onClick={() => { setOpen(false); setConfirmingRetire(true); }}
            className="flex items-center gap-2 rounded-control border-t border-border px-3 py-2 text-left text-body text-danger-text hover:bg-danger focus-visible:outline-2 focus-visible:outline-focus disabled:cursor-not-allowed disabled:text-disabled-text disabled:hover:bg-transparent"
          >
            <Archive aria-hidden className="size-4" />
            {t('lifecycle.folders.detail.action.retire')}
          </button>
        </div>
      ) : null}

      <Modal
        open={confirmingRetire}
        destructive
        title={t('lifecycle.folders.detail.action.retireTitle')}
        description={t('lifecycle.folders.detail.action.retireDescription', { name: prompt.title })}
        confirmLabel={t('lifecycle.folders.detail.action.retire')}
        confirmLoading={retireMutation.isPending}
        onClose={() => { setConfirmingRetire(false); retireMutation.reset(); }}
        onConfirm={() => retireMutation.mutate(prompt.id, { onSuccess: () => setConfirmingRetire(false) })}
      >
        {retireMutation.isError ? <p className="text-body text-danger-text">{t('lifecycle.folders.detail.action.retireError')}</p> : null}
      </Modal>
    </div>
  );
}
