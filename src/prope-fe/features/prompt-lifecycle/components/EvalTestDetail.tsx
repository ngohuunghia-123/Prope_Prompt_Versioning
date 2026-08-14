import { CheckCircle, XCircle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import type { EvalTestResult } from '@/features/prompt-lifecycle/types';

interface EvalTestDetailProps {
  test: EvalTestResult;
}

export function EvalTestDetail({ test }: EvalTestDetailProps) {
  const { t } = useTranslation();
  const variables = Object.entries(test.variables);
  return (
    <article key={test.id} className="grid min-w-0 content-start gap-5 bg-surface p-4 motion-safe:animate-navigation-panel sm:p-5">
      <header className="flex min-w-0 flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div className="min-w-0">
          <p className="text-overline font-bold tracking-navigation-overline text-muted uppercase">{t('lifecycle.evalWorkspace.testContent')}</p>
          <h2 className="mt-1 break-words font-display text-heading-3 text-ink">{test.name}</h2>
        </div>
        <span className={test.passed ? 'inline-flex items-center gap-1.5 rounded-full bg-success px-3 py-1 text-caption font-semibold text-success-text' : 'inline-flex items-center gap-1.5 rounded-full bg-danger px-3 py-1 text-caption font-semibold text-danger-text'}>
          {test.passed ? <CheckCircle aria-hidden className="size-4" weight="fill" /> : <XCircle aria-hidden className="size-4" weight="fill" />}
          {t(test.passed ? 'lifecycle.evalWorkspace.pass' : 'lifecycle.evalWorkspace.fail')}
        </span>
      </header>
      {variables.length > 0 ? (
        <section className="min-w-0" aria-labelledby="eval-variables-heading">
          <h3 id="eval-variables-heading" className="text-caption font-semibold text-ink">{t('lifecycle.evalWorkspace.variables', { count: variables.length })}</h3>
          <dl className="mt-2 grid gap-2 sm:grid-cols-2">
            {variables.map(([name, value]) => (
              <div key={name} className="rounded-lg border border-border bg-subtle p-3">
                <dt className="font-mono text-caption font-semibold text-muted">{`{{${name}}}`}</dt>
                <dd className="mt-1 break-words text-body text-ink">{value}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}
      <section className="min-w-0" aria-labelledby="eval-input-heading">
        <h3 id="eval-input-heading" className="text-caption font-semibold text-ink">{t('lifecycle.evalWorkspace.input')}</h3>
        <p className="mt-2 break-words whitespace-pre-wrap rounded-xl border border-border bg-subtle p-4 text-body text-ink">{test.input}</p>
      </section>
      <section className="min-w-0" aria-labelledby="eval-output-heading">
        <h3 id="eval-output-heading" className="text-caption font-semibold text-ink">{t('lifecycle.evalWorkspace.output')}</h3>
        <pre className="mt-2 max-w-full min-w-0 overflow-x-auto whitespace-pre-wrap break-words rounded-xl border border-border bg-subtle p-4 font-mono text-caption text-ink">{test.output}</pre>
      </section>
      <section className="min-w-0" aria-labelledby="eval-expected-heading">
        <h3 id="eval-expected-heading" className="text-caption font-semibold text-ink">{t('lifecycle.evalWorkspace.expected')}</h3>
        <pre className="mt-2 max-w-full min-w-0 overflow-x-auto whitespace-pre-wrap break-words rounded-xl border border-border bg-accent-soft p-4 font-mono text-caption text-ink">{test.expectedOutput}</pre>
      </section>
    </article>
  );
}
