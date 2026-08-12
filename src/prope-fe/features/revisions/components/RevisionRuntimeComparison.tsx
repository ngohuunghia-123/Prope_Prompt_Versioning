import { useTranslation } from 'react-i18next';
import type { PromptRevision } from '@/features/revisions/types';
import { cn } from '@/lib/cn';

interface RevisionRuntimeComparisonProps { current: PromptRevision; earlier: PromptRevision; }

export function RevisionRuntimeComparison({ current, earlier }: RevisionRuntimeComparisonProps) {
  const { t } = useTranslation();
  const fields = ['providerName', 'upstreamModel', 'temperature', 'maxTokens', 'fallbackAnswer'] as const;
  return (
    <section className="rounded-panel border border-border bg-surface p-5 shadow-panel sm:p-7" aria-labelledby="runtime-comparison-title">
      <h2 id="runtime-comparison-title" className="text-heading-3 font-semibold">{t('revisions.compare.runtimeTitle')}</h2>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-table text-left text-body">
          <thead><tr className="border-b border-border text-caption text-muted"><th className="p-3 font-semibold">{t('revisions.compare.field')}</th><th className="p-3 font-semibold">{t('revisions.compare.earlier')}</th><th className="p-3 font-semibold">{t('revisions.compare.current')}</th></tr></thead>
          <tbody>{fields.map((field) => {
            const changed = earlier[field] !== current[field];
            return <tr key={field} className="border-b border-border last:border-0"><th className="p-3 font-semibold">{t(`revisions.editor.${field}`)}</th><td className={cn('p-3', changed && 'bg-danger text-danger-text')}>{earlier[field]}</td><td className={cn('p-3', changed && 'bg-success text-success-text')}>{current[field]}</td></tr>;
          })}</tbody>
        </table>
      </div>
    </section>
  );
}
