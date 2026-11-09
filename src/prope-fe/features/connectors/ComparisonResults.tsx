import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { getComparison, type RunPair } from '@/features/connectors/api';
import { ConnectorError } from '@/features/connectors/ConnectorError';

export function ComparisonResults({ pair }: { pair: RunPair }) {
  const { t, i18n } = useTranslation();
  const query = useQuery({ queryKey: ['connector', 'comparison', pair.original_run_id, pair.candidate_run_id], queryFn: () => getComparison(pair),
    refetchInterval: (state) => {
      const value = state.state.data;
      if (state.state.error || (value && !['queued', 'running'].includes(value.original.status) && !['queued', 'running'].includes(value.candidate.status))) return false;
      return Math.min(2000 * 2 ** state.state.dataUpdateCount, 15000);
    } });
  const format = (value: number | null) => value === null ? t('connector.unavailable') : new Intl.NumberFormat(i18n.language, { maximumFractionDigits: 6 }).format(value);
  return <section className="space-y-3" aria-label={t('connector.evidence')}>
    <h3 className="font-display text-heading-3">{t('connector.evidence')}</h3>
    <ConnectorError error={query.error} />
    {query.isPending ? <p role="status">{t('common.loading')}</p> : null}
    {query.data ? <>
      <p role="status">{t(query.data.comparable ? 'connector.comparable' : 'connector.incomplete')}</p>
      <p className="text-caption text-muted">{t('connector.deterministic')}</p>
      <p>{t('connector.configurationUsed', { provider: query.data.provider_config_id, model: query.data.upstream_model })}</p>
      <pre className="whitespace-pre-wrap break-all text-caption">{JSON.stringify(query.data.parameters, null, 2)}</pre>
      {([['original', query.data.original, query.data.original_cases], ['candidate', query.data.candidate, query.data.candidate_cases]] as const).map(([side, run, cases]) => <section key={side} className="space-y-2 border-t border-border pt-3">
        <h4>{t(`connector.${side}`)}</h4>
        <p className="break-all text-caption">{run.run_id}</p>
        <p>{t('connector.status', { status: run.status })}</p>
        <p>{t('connector.counts', { passed: format(run.pass_count), failed: format(run.fail_count), errors: format(run.error_count) })}</p>
        <p>{t('connector.usage', { input: format(run.input_tokens), output: format(run.output_tokens), cost: format(run.cost_amount), currency: run.cost_currency ?? '' })}</p>
        {cases.length === 0 ? <p>{t('connector.noCases')}</p> : cases.map((item) => <details key={item.case_id} className="rounded-lg border border-border p-3">
          <summary className="cursor-pointer focus-visible:outline focus-visible:outline-focus">{t('connector.case', { id: item.case_id, outcome: item.outcome })}</summary>
          <p>{t('connector.latency', { value: format(item.latency_ms) })}</p>
          <pre className="whitespace-pre-wrap break-all text-caption">{item.output_content}</pre>
          <pre className="whitespace-pre-wrap break-all text-caption">{JSON.stringify(item.assertion_results, null, 2)}</pre>
          {item.error_code ? <p>{t('connector.error', { code: item.error_code })}</p> : null}
        </details>)}
      </section>)}
    </> : null}
    <Button intent="secondary" onClick={() => void query.refetch()}>{t('common.tryAgain')}</Button>
  </section>;
}
