import { WarningCircle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import type { PromptTestResult } from '@/features/prompt-lifecycle/types';

interface PromptTestOutputPanelProps {
  result?: PromptTestResult;
  error: boolean;
  pending: boolean;
}

export function PromptTestOutputPanel({ result, error, pending }: PromptTestOutputPanelProps) {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="prompt-test-output" aria-live="polite" className="flex min-h-80 flex-1 flex-col rounded-modal border border-border bg-surface p-5 shadow-panel sm:p-6">
      <h2 id="prompt-test-output" className="font-display text-heading-3 text-ink">{t('lifecycle.promptTest.outputTitle')}</h2>
      <div className="mt-4 flex flex-1 flex-col rounded-xl border border-border bg-subtle p-4">
        {pending ? (
          <p role="status" className="text-body text-muted">{t('lifecycle.promptTest.running')}</p>
        ) : error ? (
          <div role="alert" className="flex items-start gap-3 text-danger-text">
            <WarningCircle aria-hidden className="mt-0.5 size-5 shrink-0" />
            <p className="text-body">{t('lifecycle.promptTest.runError')}</p>
          </div>
        ) : result ? (
          <div>
            <pre className="whitespace-pre-wrap break-words font-mono text-caption text-ink">{result.output}</pre>
            <p className="mt-4 border-t border-border pt-3 text-caption text-muted">
              {t('lifecycle.promptTest.usage', { input: result.inputTokens, output: result.outputTokens })}
            </p>
          </div>
        ) : (
          <p className="text-body text-muted">{t('lifecycle.promptTest.outputPlaceholder')}</p>
        )}
      </div>
    </section>
  );
}
