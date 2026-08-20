import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { canaryMetricsOptions, canaryOptions, useCanaryMutation } from '@/features/prompt-lifecycle/canaryQueries';
import type { Canary } from '@/features/prompt-lifecycle/canaryTypes';
import type { PromptDetail, Revision } from '@/features/prompt-lifecycle/types';

const PRESETS = [5, 10, 25, 50] as const;

export function CanaryPanel({ prompt, candidate }: { prompt: PromptDetail; candidate: Revision }) {
  const { t } = useTranslation();
  const query = useQuery(canaryOptions(prompt.id));
  const mutation = useCanaryMutation(prompt.id);
  const canary = query.data ?? null;
  const metrics = useQuery(canaryMetricsOptions(canary));
  const baseline = canary?.baselineVersionId ?? prompt.revisions.find((revision) => revision.status === 'inUse')?.id ?? prompt.revisions[0]?.id;
  const start = () => {
    if (!baseline || candidate.status !== 'approved' || candidate.id === baseline) return;
    mutation.mutate({ promptId: prompt.id, baselineVersionId: baseline, candidateVersionId: candidate.id, percentage: 5, status: 'active', startedBy: 'current-user', startedAt: new Date().toISOString(), revision: 1 });
  };
  const update = (percentage: number) => { if (canary) mutation.mutate({ ...canary, percentage, revision: canary.revision + 1 }); };
  const close = (status: Canary['status']) => { if (canary) mutation.mutate({ ...canary, status, revision: canary.revision + 1 }); };
  return (
    <section aria-labelledby="canary-title" className="p-4 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 id="canary-title" className="font-display text-heading-3 text-ink">{t('lifecycle.canary.title')}</h2><p className="mt-1 text-body text-muted">{t('lifecycle.canary.description')}</p></div>{!canary || canary.status !== 'active' ? <Button disabled={candidate.status !== 'approved' || candidate.id === baseline} onClick={start}>{t('lifecycle.canary.start')}</Button> : null}</div>
      {canary?.status === 'active' ? <div className="mt-5 grid gap-5">
        <div><div className="mb-2 flex justify-between text-caption text-muted"><span>{t('lifecycle.canary.baseline', { value: 100 - canary.percentage })}</span><span>{t('lifecycle.canary.candidate', { value: canary.percentage })}</span></div><div className="flex h-3 overflow-hidden rounded-full bg-subtle"><span className="bg-secondary" style={{ width: `${100 - canary.percentage}%` }} /><span className="bg-primary" style={{ width: `${canary.percentage}%` }} /></div></div>
        <div className="flex flex-wrap gap-2">{PRESETS.map((value) => <Button key={value} intent={canary.percentage === value ? 'primary' : 'neutral'} size="small" onClick={() => update(value)}>{value}%</Button>)}</div>
        <div className="overflow-x-auto"><table className="w-full min-w-2xl text-left text-body"><thead className="border-b border-border text-caption text-muted"><tr><th className="p-3">{t('lifecycle.promptDetail.version')}</th><th className="p-3">{t('lifecycle.canary.requests')}</th><th className="p-3">{t('lifecycle.canary.error')}</th><th className="p-3">{t('lifecycle.canary.fallback')}</th><th className="p-3">{t('lifecycle.canary.latency')}</th><th className="p-3">{t('lifecycle.canary.cost')}</th></tr></thead><tbody>{(metrics.data ?? []).map((row) => <tr key={row.versionId} className="border-b border-border"><td className="p-3 font-mono">{row.versionId}</td><td className="p-3">{row.requests}</td><td className="p-3">{Math.round(row.errorRate * 1000) / 10}%</td><td className="p-3">{Math.round(row.fallbackRate * 1000) / 10}%</td><td className="p-3">{row.latencyMs} ms</td><td className="p-3">${row.cost}</td></tr>)}</tbody></table></div>
        <div className="flex flex-wrap justify-end gap-2"><Button intent="neutral" onClick={() => close('stopped')}>{t('lifecycle.canary.stop')}</Button><Button onClick={() => close('promoted')}>{t('lifecycle.canary.promote')}</Button></div>
      </div> : null}
    </section>
  );
}
