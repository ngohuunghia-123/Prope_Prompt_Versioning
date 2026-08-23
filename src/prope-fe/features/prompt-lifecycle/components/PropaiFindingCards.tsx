import { CaretRight, Fire } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';

import { cn } from '@/lib/cn';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import type { ImprovementFinding } from '@/features/prompt-lifecycle/improvementTypes';

interface PropaiFindingCardsProps {
  findings: ImprovementFinding[];
  onSelect: (finding: ImprovementFinding) => void;
}

/**
 * The PropAI suggestion cards ("Gợi ý từ PropAI").
 *
 * A card answers two questions at a glance — *why fix this* (the detector
 * sentence with its own figures) and *what is the root cause* (the triage model's
 * one sentence) — and the whole card is the button into the before/after drawer.
 * Severity `warning` renders the urgent treatment: these are findings somebody
 * should act on, not browse.
 */
export function PropaiFindingCards({ findings, onSelect }: PropaiFindingCardsProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();

  return (
    <ul className="divide-y divide-border">
      {findings.map((finding) => (
        <li key={finding.finding_id}>
          <button
            type="button"
            onClick={() => onSelect(finding)}
            className="flex w-full items-start justify-between gap-3 p-4 text-left focus-visible:outline-2 focus-visible:outline-focus sm:p-6"
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={cn(
                    'inline-flex items-center gap-1 rounded-control px-2 py-0.5 text-overline font-bold uppercase tracking-wide',
                    finding.severity === 'warning' ? 'bg-danger/10 text-danger' : 'bg-subtle text-muted',
                  )}
                >
                  {finding.severity === 'warning' ? <Fire aria-hidden className="size-3" /> : null}
                  {finding.severity === 'warning'
                    ? t('lifecycle.surface.monitoring.propai.urgent')
                    : t(`improvement.severity.${finding.severity}`)}
                </span>
                <span className="text-body font-semibold text-ink">
                  {t(`improvement.detector.${finding.detector_id}.title`)}
                </span>
              </div>
              <p className="mt-1.5 text-caption font-medium uppercase tracking-wide text-muted">
                {t('lifecycle.surface.monitoring.propai.why')}
              </p>
              <p className="text-body text-muted">
                {t(`improvement.detector.${finding.detector_id}.body`, { ...finding.params })}
              </p>
              {finding.evidence_line ? (
                <>
                  <p className="mt-1.5 text-caption font-medium uppercase tracking-wide text-muted">
                    {t('lifecycle.surface.monitoring.propai.rootCause')}
                  </p>
                  <p className="text-body text-ink">{finding.evidence_line}</p>
                </>
              ) : null}
              <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
                <span>{t('improvement.inbox.occurrences', { count: finding.occurrence_count })}</span>
                <span aria-hidden>·</span>
                <span>{t('improvement.inbox.lastSeen', { when: format.date(finding.last_seen) })}</span>
              </p>
            </div>
            <CaretRight aria-hidden className="mt-1 size-4 shrink-0 text-muted" />
          </button>
        </li>
      ))}
    </ul>
  );
}
