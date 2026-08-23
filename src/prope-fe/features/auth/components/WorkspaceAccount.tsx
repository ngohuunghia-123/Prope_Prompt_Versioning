import { Buildings, CaretUpDown, PlusCircle, SignOut } from '@phosphor-icons/react';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { useLogoutMutation } from '@/features/auth/queries';
import { useWorkspaceAccountIdentity } from '@/features/auth/components/useWorkspaceAccountIdentity';
import { cn } from '@/lib/cn';
import { useMotionPresence } from '@/lib/useMotionPresence';

export function WorkspaceAccount() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { initials, name, session } = useWorkspaceAccountIdentity();
  const logout = useLogoutMutation();
  const [open, setOpen] = useState(false);
  const motion = useMotionPresence(open, 'popover');
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const closeOutside = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false); };
    document.addEventListener('pointerdown', closeOutside);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('pointerdown', closeOutside);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [open]);

  if (!session.data) {
    return <Link to="/app/account" className="mt-1 flex min-h-13 min-w-0 items-center gap-2.5 rounded-navigation-panel bg-canvas p-2.5 text-ink shadow-inset transition-colors hover:bg-surface hover:text-link focus-visible:outline-2 focus-visible:outline-focus"><span aria-hidden className="grid size-8 shrink-0 place-items-center rounded-full bg-navigation-avatar text-overline font-bold">LP</span><span className="min-w-0"><strong className="block truncate text-navigation-strong font-semibold">{t('navigation.advanced.home.accountName')}</strong><span className="block truncate text-overline text-muted">{t('navigation.advanced.home.accountPlan')}</span></span></Link>;
  }

  const handleLogout = async () => {
    try {
      await logout.mutateAsync();
      void navigate('/login', { replace: true });
    } catch {
      setOpen(true);
    }
  };

  return (
    <div ref={containerRef} className="relative">
      {motion.mounted ? (
        <div ref={(node) => { motion.surfaceRef.current = node; }} role="menu" className={cn('absolute inset-x-0 bottom-full z-30 mb-2 overflow-hidden rounded-navigation-panel border border-border bg-surface p-1.5 shadow-floating', !open && 'pointer-events-none')}>
          <div className="flex items-center gap-2 border-b border-border px-2 py-2 text-caption text-muted">
            <Buildings aria-hidden className="size-4 shrink-0" />
            <span className="truncate">{session.data.user.workspaceName}</span>
          </div>
          <Link role="menuitem" to="/workspaces" onClick={() => setOpen(false)} className="flex items-center gap-2 rounded-navigation-control px-2 py-2 text-body text-ink hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus"><PlusCircle aria-hidden className="size-4" />{t('chooser.create.title')}</Link>
          <button role="menuitem" type="button" disabled={logout.isPending} onClick={() => void handleLogout()} className="flex w-full cursor-pointer items-center gap-2 rounded-navigation-control px-2 py-2 text-left text-body text-danger-text hover:bg-danger focus-visible:outline-2 focus-visible:outline-focus disabled:cursor-not-allowed disabled:text-disabled-text"><SignOut aria-hidden className="size-4" />{t('auth.logout')}</button>
          {logout.isError ? <p role="alert" className="px-2 py-1 text-caption text-danger-text">{t('auth.logoutError')}</p> : null}
        </div>
      ) : null}
      <button type="button" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((current) => !current)} className="flex w-full cursor-pointer items-center gap-3 rounded-xl bg-surface p-3 text-left shadow-inset transition-colors hover:bg-canvas focus-visible:outline-2 focus-visible:outline-focus">
        <span aria-hidden className="grid size-9 shrink-0 place-items-center rounded-full bg-hero text-caption font-bold text-inverse">{initials}</span>
        <span className="min-w-0 flex-1"><strong className="block truncate text-body text-ink">{name}</strong><span className="block truncate text-caption text-muted">{t(`roles.${session.data.user.role}`)} · {session.data.user.workspaceName}</span></span>
        <CaretUpDown aria-hidden className="size-4 shrink-0 text-muted" />
      </button>
    </div>
  );
}
