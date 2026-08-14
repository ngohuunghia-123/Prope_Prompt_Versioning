import { useTranslation } from 'react-i18next';
import type { PromptTestResult } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';

interface PromptTestCostPanelProps { result?: PromptTestResult; }

export function PromptTestCostPanel({ result }: PromptTestCostPanelProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const values = result
    ? [format.currency6(result.requestCost), format.currency6(result.inputCost), format.currency6(result.outputCost)]
    : ['—', '—', '—'];
  const labels = [t('lifecycle.promptTest.costPerRequest'), t('lifecycle.promptTest.inputCost'), t('lifecycle.promptTest.outputCost')];
  return (
    <section aria-labelledby="prompt-test-cost" className="rounded-modal border border-border bg-surface p-5 shadow-panel sm:p-6">
      <h2 id="prompt-test-cost" className="font-display text-heading-3 text-ink">{t('lifecycle.promptTest.costTitle')}</h2>
      <dl className="mt-4 grid grid-cols-3 divide-x divide-border rounded-xl border border-border bg-subtle">
        {labels.map((label, index) => (
          <div key={label} className="min-w-0 px-3 py-4 text-center sm:px-4">
            <dt className="text-caption text-muted">{label}</dt>
            <dd className="mt-2 truncate text-body font-semibold text-ink">{values[index]}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
