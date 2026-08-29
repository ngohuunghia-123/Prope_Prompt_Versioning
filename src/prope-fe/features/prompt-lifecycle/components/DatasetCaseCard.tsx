import { useTranslation } from 'react-i18next';
import type { EvalDatasetCase } from '@/features/prompt-lifecycle/evalTypes';

function assertionValue(value: unknown): string {
  if (value === null || value === undefined) return '';
  return typeof value === 'string' ? value : JSON.stringify(value);
}

function turnContent(turn: Record<string, unknown>): string {
  return typeof turn.content === 'string' ? turn.content : JSON.stringify(turn.content);
}

/** One test case, read-only: the conversation the runner will send, and the
 * assertions the output has to satisfy. Editing happens in the same dialog the
 * workspace uses, so this card only has to make a case legible. */
export function DatasetCaseCard({ item, ordinal }: { item: EvalDatasetCase; ordinal: number }) {
  const { t } = useTranslation();
  return (
    <div className="rounded-lg border border-border bg-subtle p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h4 className="font-medium text-ink">{item.name}</h4>
        <span className="shrink-0 text-caption text-muted">#{ordinal}</span>
      </div>
      <div className="mt-2 grid gap-1.5">
        {item.input_messages.map((turn, index) => {
          const role = typeof turn.role === 'string' ? turn.role : 'user';
          return (
            <div key={index} className="rounded border border-border/60 bg-surface p-2">
              <span className="text-caption font-semibold text-muted">
                {role === 'assistant' ? t('lifecycle.dataset.case.assistant') : t('lifecycle.dataset.case.user')}
              </span>
              <p className="mt-0.5 whitespace-pre-wrap text-caption text-ink">{turnContent(turn)}</p>
            </div>
          );
        })}
      </div>
      <div className="mt-2">
        <p className="text-caption font-semibold text-muted">{t('lifecycle.dataset.case.assertions')}</p>
        {item.assertions.length === 0 ? (
          <p className="mt-1 text-caption text-muted">{t('lifecycle.dataset.case.noAssertions')}</p>
        ) : (
          <ul className="mt-1 grid gap-1">
            {item.assertions.map((assertion, index) => (
              <li key={index} className="flex flex-wrap items-baseline gap-x-2 text-caption text-ink">
                <code className="rounded bg-subtle px-1.5 py-0.5 font-mono text-caption">{assertion.type}</code>
                <span className="break-all font-mono">{assertionValue(assertion.value)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
