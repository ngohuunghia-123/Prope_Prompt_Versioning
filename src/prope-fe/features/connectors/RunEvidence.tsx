import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { getEvalRun, getEvalRunCases, getEvalSuite } from '@/features/prompt-lifecycle/evalApi';
import { EvalRunResults } from '@/features/prompt-lifecycle/components/EvalRunResults';
import { ConnectorError } from '@/features/connectors/ConnectorError';

export function RunEvidence({ runId }: { runId: string }) {
  const { t } = useTranslation();
  const run = useQuery({ queryKey: ['connector', 'run', runId], queryFn: () => getEvalRun(runId),
    refetchInterval: (query) => query.state.error || (query.state.data && !['queued', 'running'].includes(query.state.data.status)) ? false : 3000 });
  const cases = useQuery({ queryKey: ['connector', 'runCases', runId, run.data?.status], queryFn: () => getEvalRunCases(runId),
    refetchInterval: (query) => query.state.error || run.isError || (run.data && !['queued', 'running'].includes(run.data.status)) ? false : 3000 });
  const suiteId = run.data?.suite_id ?? '';
  const suite = useQuery({ queryKey: ['connector', 'suite', suiteId], queryFn: () => getEvalSuite(suiteId), enabled: Boolean(suiteId) });
  const error = run.error ?? cases.error ?? suite.error;
  return <section className="space-y-3">
    <p className="text-caption text-muted">{t('connector.deterministic')}</p>
    <ConnectorError error={error} />
    {!error && (run.isPending || cases.isPending || suite.isPending) ? <p role="status">{t('common.loading')}</p> : null}
    {run.data && suite.data ? <EvalRunResults reports={[{ run: run.data, cases: cases.data ?? [], suite: suite.data,
      handle: { run_id: runId, suite_id: suiteId, suite_name: suite.data.name, suite_version: suite.data.suite_version, role: run.data.role } }]} /> : null}
  </section>;
}
