import { ArrowSquareOut, BookOpenText, FileText } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Drawer } from '@/components/ui/Drawer';
import { buttonVariants } from '@/components/ui/buttonVariants';
import type { Citation } from '@/features/chat/types';

interface ChatCitationPreviewProps {
  citation: Citation | null;
  onClose: () => void;
}

export function ChatCitationPreview({ citation, onClose }: ChatCitationPreviewProps) {
  const { t } = useTranslation();
  return (
    <Drawer open={citation !== null} onClose={onClose} side="right" size="compact" title={t('chat.sources.previewTitle')}>
      {citation ? (
        <article className="grid gap-4 overflow-y-auto p-5">
          <div className="flex items-start gap-3">
            <span className="grid size-9 shrink-0 place-items-center rounded-full bg-info text-info-strong">
              {citation.kind === 'prompt' ? <FileText aria-hidden className="size-5" /> : <BookOpenText aria-hidden className="size-5" />}
            </span>
            <div className="min-w-0">
              <p className="text-overline font-semibold uppercase tracking-navigation-overline text-muted">{t(`chat.sources.kind.${citation.kind}`, { defaultValue: citation.kind })}</p>
              <h3 className="mt-1 text-body font-semibold text-ink">{citation.label}</h3>
              {citation.document ? <p className="mt-1 text-overline text-muted">{citation.document}</p> : null}
            </div>
          </div>
          <div className="rounded-navigation-panel border border-border bg-canvas p-3">
            <p className="text-overline font-semibold uppercase tracking-navigation-overline text-muted">{t('chat.sources.supportingExcerpt')}</p>
            <p className="mt-2 whitespace-pre-wrap text-caption leading-relaxed text-ink">{citation.excerpt || t('chat.sources.noExcerpt')}</p>
          </div>
          {citation.href ? (
            <a href={citation.href} onClick={onClose} className={buttonVariants({ intent: 'primary' })}>
              {t('chat.sources.openPrompt')}<ArrowSquareOut aria-hidden className="size-4" />
            </a>
          ) : null}
        </article>
      ) : null}
    </Drawer>
  );
}
