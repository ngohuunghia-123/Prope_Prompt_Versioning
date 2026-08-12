import { useTranslation } from 'react-i18next';
import type { PreservedPrompt } from '@/features/preservation/types';

interface PromptRuntimeSummaryProps { prompt: PreservedPrompt; }

export function PromptRuntimeSummary({ prompt }: PromptRuntimeSummaryProps) {
  const { t } = useTranslation();
  const items = [
    ['modelName', prompt.modelName], ['providerName', prompt.providerName], ['upstreamModel', prompt.upstreamModel],
    ['temperature', prompt.temperature], ['maxTokens', prompt.maxTokens], ['fallbackAnswer', prompt.fallbackAnswer],
  ] as const;
  return (
    <section className="mt-5 rounded-modal border border-border bg-canvas p-5" aria-labelledby="runtime-summary-title">
      <h2 id="runtime-summary-title" className="text-heading-3 font-semibold">{t('preservation.detail.runtimeTitle')}</h2>
      <dl className="mt-4 grid gap-4 sm:grid-cols-2">{items.map(([key, value]) => <div key={key}><dt className="text-caption text-muted">{t(`preservation.detail.${key}`)}</dt><dd className="mt-1 break-words text-body font-semibold">{value}</dd></div>)}</dl>
    </section>
  );
}
