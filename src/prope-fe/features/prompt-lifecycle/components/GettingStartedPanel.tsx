import { FileArrowUp, MagnifyingGlass, MapTrifold, Question, Sparkle } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Modal } from '@/components/ui/Modal';
import { NavigationSearchPanel } from '@/components/NavigationSearchPanel';
import { useNavigationMode } from '@/components/useNavigationMode';
import { useChat } from '@/features/chat/ChatContext';
import { useWorkspaceAccountIdentity } from '@/features/auth/components/useWorkspaceAccountIdentity';

export function GettingStartedPanel() {
  const { t } = useTranslation();
  const { name } = useWorkspaceAccountIdentity();
  const { setMode } = useNavigationMode();
  const { send } = useChat();
  const [searchOpen, setSearchOpen] = useState(false);

  const openChat = (message?: string) => {
    setMode('chat');
    if (message) send(message);
  };

  return (
    <>
      <section className="rounded-modal border border-border bg-surface p-5 shadow-panel sm:p-6" aria-labelledby="getting-started-title">
        <div className="flex items-start gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent-soft text-secondary"><Sparkle aria-hidden className="size-5" weight="fill" /></span>
          <div className="min-w-0">
            <p className="text-overline font-bold uppercase tracking-navigation-overline text-muted">{t('lifecycle.quickActions.eyebrow')}</p>
            <h2 id="getting-started-title" className="mt-1 font-display text-heading-2 text-ink">{t('lifecycle.quickActions.title', { username: name })}</h2>
          </div>
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-3">
          <button type="button" onClick={() => setSearchOpen(true)} className="flex items-start gap-3 rounded-xl border border-border bg-canvas p-4 text-left transition-colors hover:border-secondary hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus">
            <MagnifyingGlass aria-hidden className="mt-0.5 size-5 shrink-0 text-secondary" />
            <span><strong className="block text-body font-semibold text-ink">{t('lifecycle.quickActions.searchTitle')}</strong><span className="mt-1 block text-caption text-muted">{t('lifecycle.quickActions.searchBody')}</span></span>
          </button>
          <button type="button" onClick={() => openChat(t('lifecycle.quickActions.bulkImportPrompt'))} className="flex items-start gap-3 rounded-xl border border-border bg-canvas p-4 text-left transition-colors hover:border-secondary hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus">
            <FileArrowUp aria-hidden className="mt-0.5 size-5 shrink-0 text-secondary" />
            <span><strong className="block text-body font-semibold text-ink">{t('lifecycle.quickActions.bulkImportTitle')}</strong><span className="mt-1 block text-caption text-muted">{t('lifecycle.quickActions.bulkImportBody')}</span></span>
          </button>
          <button type="button" onClick={() => openChat()} className="flex items-start gap-3 rounded-xl border border-border bg-canvas p-4 text-left transition-colors hover:border-secondary hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus">
            <Question aria-hidden className="mt-0.5 size-5 shrink-0 text-secondary" />
            <span><strong className="block text-body font-semibold text-ink">{t('lifecycle.quickActions.askTitle')}</strong><span className="mt-1 block text-caption text-muted">{t('lifecycle.quickActions.askBody')}</span></span>
          </button>
        </div>
        <div className="mt-3 flex w-full items-start gap-3 rounded-xl border border-dashed border-border bg-canvas p-4 text-left text-muted">
          <MapTrifold aria-hidden className="mt-0.5 size-5 shrink-0" />
          <span><strong className="block text-body font-semibold text-ink">{t('lifecycle.quickActions.tourTitle')}</strong><span className="mt-1 block text-caption">{t('lifecycle.quickActions.tourBody')}</span></span>
        </div>
      </section>
      <Modal open={searchOpen} title={t('lifecycle.quickActions.searchTitle')} description={t('lifecycle.quickActions.searchBody')} confirmLabel={t('common.close')} showCancel={false} onClose={() => setSearchOpen(false)} onConfirm={() => setSearchOpen(false)} className="max-w-xl">
        <div className="h-96"><NavigationSearchPanel onAskPropAI={(query) => { setSearchOpen(false); openChat(query); }} /></div>
      </Modal>
    </>
  );
}
