import { useTranslation } from 'react-i18next';

import { caseTotal, type EvalRunSummary } from '@/features/prompt-lifecycle/insightsTypes';
import { useInsightsFormat } from '@/features/prompt-lifecycle/useInsightsFormat';
import { cn } from '@/lib/cn';

interface EvaluationRevisionTrendProps {
  /** Every revision's runs for this prompt, newest first. */
  runs: EvalRunSummary[];
  /** `version_id` to the label the version rail shows, e.g. `r12`. */
  revisionLabels: Record<string, string>;
  /** The revision currently selected in the rail, so the reader can find it. */
  selectedVersionId: string | null;
}

/**
 * Pass rate per revision, oldest on the left.
 *
 * **This is the tab's reason to exist.** A single revision's pass rate says
 * whether it works; the sequence says whether the last edit made things worse,
 * which is the question somebody about to approve a release is actually asking.
 *
 * Bars rather than a chart library: the value is a fraction, the axis is
 * ordinal, and the whole series is a handful of revisions. A dependency to draw
 * eight rectangles would be a dependency to keep patched.
 *
 * A revision whose runs reached no cases is drawn as a gap, not as zero — the
 * two mean opposite things and the difference is the whole point of the row.
 */
export function EvaluationRevisionTrend({
  runs,
  revisionLabels,
  selectedVersionId,
}: EvaluationRevisionTrendProps) {
  const { t } = useTranslation();
  const format = useInsightsFormat();

  // Latest run of each suite, per revision — same rule as the KPI grid, so the
  // trend's last point equals the number in the tile above it.
  const seen = new Set<string>();
  const perRevision = new Map<string, { passed: number; cases: number }>();
  const order: string[] = [];

  for (const run of runs) {
    const key = `${run.version_id}::${run.suite_id}`;
    if (seen.has(key)) continue;
    seen.add(key);

    if (!perRevision.has(run.version_id)) {
      perRevision.set(run.version_id, { passed: 0, cases: 0 });
      order.push(run.version_id);
    }
    const totals = perRevision.get(run.version_id)!;
    totals.passed += run.pass_count;
    totals.cases += caseTotal(run);
  }

  // `runs` arrives newest first; a trend reads left to right through time.
  const points = order
    .reverse()
    .map((versionId) => {
      const totals = perRevision.get(versionId)!;
      return {
        versionId,
        label: revisionLabels[versionId] ?? versionId.slice(-4),
        rate: totals.cases === 0 ? null : totals.passed / totals.cases,
      };
    });

  if (points.length < 2) return null;

  return (
    <section
      aria-label={t('lifecycle.insights.evaluation.trendLabel')}
      className="bg-surface p-4 sm:p-6"
    >
      <h3 className="text-overline font-bold tracking-navigation-overline text-muted uppercase">
        {t('lifecycle.insights.evaluation.trendTitle')}
      </h3>
      <ol className="mt-5 flex items-end gap-3 overflow-x-auto pb-1">
        {points.map((point) => (
          <li key={point.versionId} className="flex min-w-16 flex-1 flex-col items-center gap-2">
            <span className="text-caption font-medium text-ink">
              {point.rate === null ? '—' : format.percent(point.rate)}
            </span>
            <span className="flex h-24 w-full items-end rounded-control bg-subtle" aria-hidden>
              {point.rate === null ? null : (
                <span
                  className={cn(
                    'w-full rounded-control',
                    point.versionId === selectedVersionId ? 'bg-secondary' : 'bg-secondary/45',
                  )}
                  style={{ height: `${Math.max(2, Math.round(point.rate * 100))}%` }}
                />
              )}
            </span>
            <span
              className={cn(
                'text-caption',
                point.versionId === selectedVersionId ? 'font-semibold text-ink' : 'text-muted',
              )}
            >
              {point.label}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
