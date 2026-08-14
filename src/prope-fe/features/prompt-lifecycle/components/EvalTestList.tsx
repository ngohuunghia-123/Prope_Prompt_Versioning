import { CheckCircle, XCircle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';
import type { EvalTestResult } from '@/features/prompt-lifecycle/types';

interface EvalTestListProps {
  tests: EvalTestResult[];
  selectedId: string;
  onSelect: (testId: string) => void;
}

export function EvalTestList({ tests, selectedId, onSelect }: EvalTestListProps) {
  const { t } = useTranslation();
  return (
    <section className="flex min-h-0 min-w-0 flex-col overflow-hidden border-b border-border bg-subtle lg:border-r lg:border-b-0">
      <header className="border-b border-border bg-surface px-4 py-3">
        <h2 className="text-overline font-bold tracking-navigation-overline text-muted uppercase">{t('lifecycle.evalWorkspace.testRuns')}</h2>
        <p className="mt-1 text-caption text-muted">{t('lifecycle.evalWorkspace.testRunsCount', { count: tests.length })}</p>
      </header>
      <div className="grid min-w-0 max-h-72 gap-2 overflow-y-auto overflow-x-hidden p-3 lg:max-h-none">
        {tests.map((test, index) => {
          const selected = test.id === selectedId;
          return (
            <button
              key={test.id}
              type="button"
              onClick={() => onSelect(test.id)}
              aria-current={selected ? 'true' : undefined}
              className={cn('flex w-full min-w-0 items-center gap-3 overflow-hidden rounded-xl border px-3 py-3 text-left transition-[background-color,border-color,transform] focus-visible:outline-2 focus-visible:outline-focus active:scale-(--prope-scale-press)', selected ? 'border-focus bg-surface shadow-raised' : 'border-border bg-canvas hover:bg-surface')}
            >
              <span className="grid size-7 shrink-0 place-items-center rounded-full bg-subtle text-caption font-semibold text-ink">{String(index + 1).padStart(2, '0')}</span>
              <span className="block min-w-0 flex-1 overflow-hidden text-ellipsis whitespace-nowrap text-body font-medium text-ink">{test.name}</span>
              {test.passed ? <CheckCircle aria-label={t('lifecycle.evalWorkspace.pass')} className="size-5 shrink-0 text-success-text" weight="fill" /> : <XCircle aria-label={t('lifecycle.evalWorkspace.fail')} className="size-5 shrink-0 text-danger-text" weight="fill" />}
            </button>
          );
        })}
      </div>
    </section>
  );
}
