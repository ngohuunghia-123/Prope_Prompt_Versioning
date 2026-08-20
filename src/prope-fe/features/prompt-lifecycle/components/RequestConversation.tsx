import { useTranslation } from 'react-i18next';

import type { TraceMessage } from '@/features/prompt-lifecycle/traceTypes';
import { cn } from '@/lib/cn';

interface RequestConversationProps {
  messages: TraceMessage[];
}

export function RequestConversation({ messages }: RequestConversationProps) {
  const { t } = useTranslation();

  return (
    <section aria-label={t('lifecycle.insights.trace.requestTitle')} className="grid gap-4">
      <header>
        <h3 className="font-display text-heading-3 text-ink">
          {t('lifecycle.insights.trace.requestTitle')}
        </h3>
        <p className="mt-1 text-caption text-muted">
          {t('lifecycle.insights.trace.requestDescription')}
        </p>
      </header>

      <ol className="grid list-none gap-3 p-0">
        {messages.map((message) => (
          <li
            key={message.message_id}
            className={cn(
              'grid max-w-[85%] gap-1',
              message.role === 'user' && 'ml-auto justify-items-end',
              message.role === 'system' && 'max-w-full',
            )}
          >
            <span className="text-overline font-bold tracking-navigation-overline text-muted uppercase">
              {t(`lifecycle.insights.trace.roles.${message.role}`)}
            </span>
            <p
              className={cn(
                'whitespace-pre-wrap rounded-xl border border-border bg-canvas px-4 py-3 text-body text-ink',
                message.role === 'user' && 'border-accent bg-accent-soft',
                message.role === 'system' && 'w-full border-dashed text-muted',
              )}
            >
              {message.content}
            </p>
          </li>
        ))}
      </ol>
    </section>
  );
}
