import { useTranslation } from 'react-i18next';

import { StatusBadge } from '@/components/StatusBadge';
import { evidenceTotals, type ReviewScreen } from '@/features/prompt-lifecycle/releaseTypes';
import { useInsightsFormat } from '@/features/prompt-lifecycle/useInsightsFormat';

interface ReleaseEvidenceProps {
  screen: ReviewScreen;
}

/**
 * `CostEvidence`, read defensively.
 *
 * The field is typed `dict[str, Any]` on the wire, so its keys are a convention
 * rather than a contract, and money crosses as a string (A-107 forbids currency
 * conversion, so the amount is never a float here). A delta that cannot be read
 * renders as "unknown" — never as zero, which would read as "no change".
 */
function readDelta(delta: Record<string, unknown> | null): { cost: number; currency: string } | null {
  if (!delta) return null;
  const amount = Number(delta.cost);
  const currency = delta.currency;
  if (!Number.isFinite(amount) || typeof currency !== 'string' || !currency) return null;
  return { cost: amount, currency };
}

/**
 * What the approver is deciding on: the eval evidence and the cost delta.
 *
 * **Absent evidence is stated, never rendered as zero.** `summary_available` is
 * false when no run has been recorded for this revision, which is a different
 * fact from "the run found nothing wrong" — and it is the case the server then
 * demands a written acknowledgement for.
 */
export function ReleaseEvidence({ screen }: ReleaseEvidenceProps) {
  const { t } = useTranslation();
  const format = useInsightsFormat();
  const totals = evidenceTotals(screen.summary);

  return (
    <section className="rounded-modal border border-border bg-surface p-5 shadow-panel" aria-labelledby="release-evidence-title">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <h2 id="release-evidence-title" className="font-display text-heading-3 text-ink">
          {t('lifecycle.release.evidenceTitle')}
        </h2>
        {screen.acknowledgement_required ? (
          <StatusBadge tone="pending">{t('lifecycle.release.acknowledgementRequired')}</StatusBadge>
        ) : null}
      </div>

      {!screen.summary_available || !screen.summary || screen.summary.suites.length === 0 ? (
        <p className="mt-3 max-w-prose text-body text-muted">{t('lifecycle.release.noEvidence')}</p>
      ) : (
        <>
          {totals ? (
            <p className="mt-3 text-body text-ink">
              {t('lifecycle.release.evidenceTotals', {
                passed: totals.passed,
                cases: totals.cases,
                suites: screen.summary.suites.length,
              })}
            </p>
          ) : null}

          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-160 border-collapse text-left text-body">
              <thead>
                <tr className="border-b border-border text-caption text-muted">
                  <th scope="col" className="py-2 pr-4 font-normal">{t('lifecycle.release.columns.suite')}</th>
                  <th scope="col" className="py-2 pr-4 font-normal">{t('lifecycle.release.columns.result')}</th>
                  <th scope="col" className="py-2 pr-4 font-normal">{t('lifecycle.release.columns.errors')}</th>
                  <th scope="col" className="py-2 font-normal">{t('lifecycle.release.columns.costDelta')}</th>
                </tr>
              </thead>
              <tbody>
                {screen.summary.suites.map((suite) => (
                  <tr key={suite.run_id} className="border-b border-border/60 last:border-0">
                    <td className="py-2.5 pr-4 text-ink">
                      {suite.suite_name}
                      <span className="ml-2 text-caption text-muted">v{suite.suite_version}</span>
                    </td>
                    <td className="py-2.5 pr-4">
                      <span className={suite.fail_count > 0 ? 'text-danger-text' : 'text-ink'}>
                        {suite.pass_count}/{suite.case_count}
                      </span>
                    </td>
                    <td className="py-2.5 pr-4 text-muted">{suite.error_count}</td>
                    <td className="py-2.5 text-muted">{(() => {
                      const delta = readDelta(suite.cost_delta);
                      return delta ? format.money(delta.cost, delta.currency) : t('lifecycle.insights.usageUnknown');
                    })()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {screen.summary.cost_warning ? (
            <p className="mt-3 text-caption text-warning-strong">{t('lifecycle.release.costWarning')}</p>
          ) : null}
        </>
      )}

      <dl className="mt-5 grid gap-x-8 gap-y-3 border-t border-border pt-4 sm:grid-cols-3">
        <div>
          <dt className="text-caption text-muted">{t('lifecycle.release.author')}</dt>
          <dd className="mt-1 text-body text-ink">{screen.revision.author_id}</dd>
        </div>
        <div>
          <dt className="text-caption text-muted">{t('lifecycle.release.changeSummary')}</dt>
          <dd className="mt-1 text-body text-ink">{screen.revision.change_summary || '—'}</dd>
        </div>
        <div>
          <dt className="text-caption text-muted">{t('lifecycle.release.revisionsSince')}</dt>
          <dd className="mt-1 text-body text-ink">{screen.revisions_since}</dd>
        </div>
      </dl>
    </section>
  );
}
