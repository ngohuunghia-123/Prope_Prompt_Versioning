import { ArrowClockwise, PaperPlaneRight, Trash } from '@phosphor-icons/react';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { Notification } from '@/components/Notification';
import { Button } from '@/components/ui/Button';
import type { Turn } from '@/features/prompt-lifecycle/components/useTrialChat';

interface PlaygroundChatProps {
  turns: Turn[];
  streaming: boolean;
  error?: string;
  /** False when neither the revision nor the settings panel yields a binding. */
  bindable: boolean;
  /** `{{variable}}` names with no value yet — the composer stays shut until they have one. */
  missingVariables: string[];
  onSubmit: (content: string) => void;
  onRetry: () => void;
  onReset: () => void;
}

/**
 * The chat surface, and only the chat surface.
 *
 * Everything that is not the conversation has moved off this component: the
 * meter is `PlaygroundMeter`, the model and the sampling controls are
 * `PlaygroundSettings`, and the thread itself lives in `useTrialChat`. What is
 * left renders turns and takes one message, which is what a chat box is.
 */
export function PlaygroundChat({
  turns,
  streaming,
  error,
  bindable,
  missingVariables,
  onSubmit,
  onRetry,
  onReset,
}: PlaygroundChatProps) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState('');
  const transcriptRef = useRef<HTMLDivElement>(null);

  // Follow the stream. `scrollTop = scrollHeight` rather than `scrollIntoView`
  // so the page behind the panel never moves — a chat that scrolls the whole
  // document out from under somebody reading the settings is worse than one
  // that does not follow at all.
  useEffect(() => {
    const node = transcriptRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [turns]);

  const blocked = !bindable || missingVariables.length > 0;

  function submit() {
    if (blocked || streaming || draft.trim() === '') return;
    onSubmit(draft);
    setDraft('');
  }

  return (
    <Card
      title={t('lifecycle.playground.chatTitle')}
      description={t('lifecycle.playground.chatDescription')}
      className="min-h-full"
      action={
        turns.length > 0 ? (
          <Button
            type="button"
            intent="ghost"
            size="small"
            leadingIcon={<Trash aria-hidden className="size-4" />}
            onClick={onReset}
          >
            {t('lifecycle.playground.clear')}
          </Button>
        ) : null
      }
    >
      {!bindable ? (
        <Notification tone="info" title={t('lifecycle.playground.unbound')}>
          {t('lifecycle.playground.unboundHint')}
        </Notification>
      ) : null}

      {error ? (
        <Notification tone="error" title={t('lifecycle.playground.turnFailed')}>
          {error}
        </Notification>
      ) : null}

      <div
        ref={transcriptRef}
        aria-live="polite"
        aria-label={t('lifecycle.playground.transcript')}
        className="grid max-h-[32rem] min-h-64 content-start gap-3 overflow-y-auto rounded-modal border border-border bg-canvas p-4"
      >
        {turns.length === 0 ? (
          <p className="m-auto max-w-prose text-center text-caption text-muted">
            {t('lifecycle.playground.emptyTranscript')}
          </p>
        ) : (
          turns.map((turn, index) => (
            <div
              key={`${turn.role}-${index}`}
              className={
                turn.role === 'user'
                  ? 'justify-self-end rounded-modal bg-primary px-4 py-2.5 text-body text-inverse sm:max-w-[80%]'
                  : 'justify-self-start whitespace-pre-wrap rounded-modal border border-border bg-surface px-4 py-2.5 text-body text-ink sm:max-w-[85%]'
              }
            >
              {turn.content}
              {turn.pending && turn.content === '' ? (
                <span className="text-muted">{t('lifecycle.playground.thinking')}</span>
              ) : null}
            </div>
          ))
        )}
      </div>

      <div className="grid gap-2">
        <textarea
          aria-label={t('lifecycle.playground.messageLabel')}
          value={draft}
          rows={3}
          disabled={blocked}
          placeholder={
            missingVariables.length > 0
              ? t('lifecycle.playground.fillVariablesFirst')
              : t('lifecycle.playground.messagePlaceholder')
          }
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            // Enter sends, Shift+Enter breaks the line. The opposite of a code
            // editor and the same as every chat client, which is what this is.
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
          className="min-h-20 w-full resize-y rounded-lg border border-border bg-surface px-3 py-3 text-body font-normal text-ink shadow-inset outline-none transition-colors duration-(--prope-motion-duration-fast) placeholder:text-muted focus:border-focus focus:ring-2 focus:ring-focus/25 disabled:cursor-not-allowed disabled:bg-disabled disabled:text-disabled-text"
        />
        <div className="flex flex-wrap justify-end gap-2">
          {error && turns.length > 0 ? (
            <Button
              type="button"
              intent="neutral"
              leadingIcon={<ArrowClockwise aria-hidden className="size-4" />}
              disabled={streaming}
              onClick={onRetry}
            >
              {t('lifecycle.playground.retry')}
            </Button>
          ) : null}
          <Button
            type="button"
            loading={streaming}
            disabled={blocked || draft.trim() === ''}
            trailingIcon={<PaperPlaneRight aria-hidden weight="fill" className="size-4" />}
            onClick={submit}
          >
            {t('lifecycle.playground.send')}
          </Button>
        </div>
      </div>
    </Card>
  );
}
