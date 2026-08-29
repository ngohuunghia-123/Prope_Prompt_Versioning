import { Sparkle, Wrench } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Notification } from '@/components/Notification';
import { Tag } from '@/components/Tag';
import { useAnalyzeEvalRunsMutation } from '@/features/prompt-lifecycle/queries';
import { useManualImprovementRun } from '@/features/prompt-lifecycle/components/useManualImprovementRun';

interface EvalAnalysisBriefProps {
  promptId: string;
  versionId: string;
  /** True once the revision has terminal runs and none still moving. */
  canAnalyze: boolean;
  /** Why the button is disabled — shown beside it instead of a dead control. */
  disabledReason?: string;
}

/** The advisor's "what should change?" read of the finished runs.
 *
 * The brief is one paragraph; the findings are the failure groups behind it,
 * each with fixed advice per assertion type. The editor link is where the
 * advice becomes action — carrying `?version=` so the editor opens on the
 * revision the findings describe, not on whatever is newest by then. */
export function EvalAnalysisBrief({ promptId, versionId, canAnalyze, disabledReason }: EvalAnalysisBriefProps) {
  const { t } = useTranslation();
  const analysis = useAnalyzeEvalRunsMutation(promptId);
  // ADR-0070: the propose-fix action. One click drafts an authored edit from
  // these findings, rails-checks it, gates it against the failing suite, and
  // parks it as a proposal — the run itself carries the outcome.
  const improve = useManualImprovementRun(promptId);
  const hasFindings = (analysis.data?.findings.length ?? 0) > 0;

  return (
    <section className="rounded-modal border border-border bg-surface p-5 shadow-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="grid gap-0.5">
          <h2 className="font-display text-heading-3 text-ink">{t('lifecycle.evalAdvisor.analyzeTitle')}</h2>
          <p className="text-caption text-muted">{t('lifecycle.evalAdvisor.analyzeHint')}</p>
        </div>
        <div className="flex items-center gap-2">
          {!canAnalyze && disabledReason ? <span className="text-caption text-muted">{disabledReason}</span> : null}
          <Button
            type="button"
            intent="neutral"
            size="small"
            loading={analysis.isPending}
            disabled={!canAnalyze}
            disabledReason={disabledReason}
            leadingIcon={<Sparkle aria-hidden weight="fill" className="size-4" />}
            onClick={() => analysis.mutate({ versionId })}
          >
            {t('lifecycle.evalAdvisor.analyze')}
          </Button>
          {hasFindings ? (
            <Button
              type="button"
              intent="primary"
              size="small"
              loading={improve.start.isPending}
              leadingIcon={<Wrench aria-hidden weight="fill" className="size-4" />}
              onClick={() => improve.start.mutate({ versionId, evidenceSource: 'eval_analysis' })}
            >
              {t('lifecycle.evalAdvisor.proposeFix')}
            </Button>
          ) : null}
        </div>
      </div>
      {improve.start.isError ? (
        <div className="mt-3">
          <Notification tone="error" title={t('lifecycle.evalAdvisor.proposeFixError')}>
            {t('lifecycle.evalAdvisor.proposeFixErrorHint')}
          </Notification>
        </div>
      ) : null}
      {improve.start.isSuccess ? (
        <div className="mt-3">
          <Notification tone="success" title={t('lifecycle.evalAdvisor.proposeFixStarted')}>
            {t('lifecycle.evalAdvisor.proposeFixStartedHint')}
          </Notification>
        </div>
      ) : null}
      {analysis.isError ? (
        <div className="mt-3">
          <Notification tone="error" title={t('lifecycle.evalAdvisor.analyzeError')}>
            {t('lifecycle.evalAdvisor.analyzeErrorHint')}
          </Notification>
        </div>
      ) : null}
      {analysis.data ? (
        <div className="mt-3 grid gap-3">
          <p className="text-body text-ink">{analysis.data.brief}</p>
          {analysis.data.findings.length ? (
            <ul className="grid gap-2">
              {analysis.data.findings.map((finding) => (
                <li key={`${finding.suite_name}:${finding.assertion_type}`} className="rounded-control border border-border bg-subtle p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Tag state={finding.severity === 'warning' ? 'warning' : 'neutral'}>{finding.issue}</Tag>
                    <span className="text-caption text-muted">
                      {finding.suite_name} · {finding.assertion_type} · {t('lifecycle.evalAdvisor.failedOf', { failed: finding.failed, total: finding.total })}
                    </span>
                  </div>
                  <p className="mt-1.5 text-caption text-ink">{finding.advice}</p>
                </li>
              ))}
            </ul>
          ) : null}
          <Link
            to={`/app/prompts/${encodeURIComponent(promptId)}/edit?version=${encodeURIComponent(versionId)}`}
            className="w-fit rounded-lg text-caption font-medium text-link underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-focus"
          >
            {t('lifecycle.evalAdvisor.openEditor')}
          </Link>
        </div>
      ) : null}
    </section>
  );
}
