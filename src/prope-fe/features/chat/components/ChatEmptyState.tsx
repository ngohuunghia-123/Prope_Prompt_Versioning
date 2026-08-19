import { MagnifyingGlass, ShieldCheck, Sparkle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { useChat } from '@/features/chat/ChatContext';

const suggestions = ['findPrompt', 'checkDuplicate', 'importPrompt', 'explainApproval'] as const;

export function ChatEmptyState() {
  const { t } = useTranslation();
  const { send } = useChat();
  return (
    <div className="m-auto grid w-full max-w-72 gap-3 py-4 text-center">
      <span className="mx-auto grid size-12 place-items-center overflow-hidden rounded-full bg-info">
        <img src="/assets/propai-thinking.gif" alt="" className="size-full object-cover motion-reduce:hidden" />
        <Sparkle aria-hidden className="hidden size-6 text-info-strong motion-reduce:block" />
      </span>
      <div><h3 className="text-body font-semibold text-ink">{t('chat.empty.title')}</h3><p className="mt-1 text-caption leading-relaxed text-muted">{t('chat.empty.description')}</p></div>
      <div className="grid gap-1.5 text-left">
        {suggestions.map((suggestion) => (
          <button key={suggestion} type="button" onClick={() => send(t(`chat.empty.suggestion.${suggestion}`))} className="flex min-h-10 cursor-pointer items-center gap-2 rounded-navigation-panel border border-border bg-surface px-2.5 py-2 text-caption text-ink shadow-inset hover:-translate-y-px hover:border-secondary hover:shadow-raised focus-visible:outline-2 focus-visible:outline-focus motion-reduce:hover:translate-y-0">
            <MagnifyingGlass aria-hidden className="size-3.5 shrink-0 text-link" /><span>{t(`chat.empty.suggestion.${suggestion}`)}</span>
          </button>
        ))}
      </div>
      <p className="flex items-start gap-1.5 text-left text-overline leading-relaxed text-muted"><ShieldCheck aria-hidden className="mt-0.5 size-3.5 shrink-0 text-success-text" />{t('chat.empty.disclaimer')}</p>
    </div>
  );
}
