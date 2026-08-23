import { Archive, DotsThree, Eye, PencilSimple } from '@phosphor-icons/react';
import { createPortal } from 'react-dom';
import { useEffect, useRef, useState, type CSSProperties, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Modal } from '@/components/ui/Modal';
import { useRetirePromptMutation } from '@/features/prompt-lifecycle/queries';
import type { Prompt } from '@/features/prompt-lifecycle/types';
import { cn } from '@/lib/cn';
import { useMotionPresence } from '@/lib/useMotionPresence';

interface PromptActionsMenuProps {
  folderId: string;
  prompt: Prompt;
}

export function PromptActionsMenu({ folderId, prompt }: PromptActionsMenuProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const retireMutation = useRetirePromptMutation(folderId);
  const [open, setOpen] = useState(false);
  const motion = useMotionPresence(open, 'popover');
  const [menuStyle, setMenuStyle] = useState<CSSProperties>({});
  const [confirmingRetire, setConfirmingRetire] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const retireBlocked = prompt.status === 'inUse' || prompt.status === 'retired';

  const navigateTo = (path: string) => {
    setOpen(false);
    void navigate(path, { state: { promptTitle: prompt.title } });
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') setOpen(false);
  };

  useEffect(() => {
    if (!open) return;
    const placeMenu = () => {
      const rect = triggerRef.current?.getBoundingClientRect();
      if (!rect) return;
      const menuHeight = menuRef.current?.getBoundingClientRect().height ?? 0;
      const top = rect.bottom + menuHeight > window.innerHeight
        ? rect.top - menuHeight - 4
        : rect.bottom + 4;
      setMenuStyle({ position: 'fixed', right: window.innerWidth - rect.right, top });
    };
    const closeOutside = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!triggerRef.current?.contains(target) && !menuRef.current?.contains(target)) setOpen(false);
    };
    placeMenu();
    window.addEventListener('resize', placeMenu);
    window.addEventListener('scroll', placeMenu, true);
    document.addEventListener('pointerdown', closeOutside);
    return () => {
      window.removeEventListener('resize', placeMenu);
      window.removeEventListener('scroll', placeMenu, true);
      document.removeEventListener('pointerdown', closeOutside);
    };
  }, [motion.mounted, open]);

  return (
    <div
      className="relative"
      onClick={(event) => event.stopPropagation()}
      onKeyDown={handleKeyDown}
    >
      <button
        ref={triggerRef}
        type="button"
        aria-label={t('lifecycle.folders.detail.action.menu')}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className="inline-flex size-8 items-center justify-center rounded-lg text-muted transition-colors hover:bg-subtle hover:text-ink focus-visible:outline-2 focus-visible:outline-focus"
      >
        <DotsThree aria-hidden weight="bold" className="size-5" />
      </button>

      {motion.mounted ? createPortal(
        <div ref={(node) => { menuRef.current = node; motion.surfaceRef.current = node; }} role="menu" style={menuStyle} className={cn('z-50 grid min-w-48 gap-1 rounded-lg border border-border bg-surface p-1 shadow-floating', !open && 'pointer-events-none')}>
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
        </div>, document.body,
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
