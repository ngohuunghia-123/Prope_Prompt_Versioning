import { ArrowRight, Check, CircleNotch, Minus, Warning } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { BottomSheet } from '@/components/ui/BottomSheet';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/cn';
import type { SimilarityStep, SimilarityStepName } from '@/features/prompt-lifecycle/types';

/** The rungs, in the order the funnel runs them.
 *
 * Written out here rather than derived from the events, because a rung that has
 * not reported yet still has to be on screen: the point of the sheet is that a
 * person can see what is left, and a list that grows as it goes tells them only
 * where it has been. */
// The order they run in, which is not the order a reader would guess: the
// output contracts are extracted AFTER the adjudicator has spoken, so that a
// candidate it called unrelated never costs an extraction. Keep this in step
// with `comparison/trace.py`'s `Step` — a progress list that reports rungs out
// of order is worse than one that reports nothing.
const STEPS: SimilarityStepName[] = [
  'retrieval',
  'prefilter',
  'adjudication',
  'output_contract',
  'contracts',
  'verdict',
];

type RowState = 'pending' | 'running' | 'done' | 'skipped' | 'failed';

const ICONS = {
  pending: <Minus aria-hidden className="size-4" />,
  running: <CircleNotch aria-hidden className="size-4 animate-spin" />,
  done: <Check aria-hidden className="size-4" weight="bold" />,
  skipped: <Minus aria-hidden className="size-4" />,
  failed: <Warning aria-hidden className="size-4" weight="fill" />,
} as const;

const TONE = {
  pending: 'border-border text-muted',
  running: 'border-secondary bg-secondary/15 text-secondary',
  done: 'border-primary bg-primary/10 text-primary',
  skipped: 'border-border text-muted',
  failed: 'border-danger bg-danger/10 text-danger',
} as const;

/** The last thing this rung said, and nothing before it.
 *
 * `started` then `done` is one row moving, not two rows: the trace is a picture
 * of the funnel, and the funnel has six rungs however many frames it sent. */
function rowState(events: SimilarityStep[], step: SimilarityStepName): RowState {
  const latest = [...events].reverse().find((event) => event.step === step);
  if (!latest) return 'pending';
  if (latest.state === 'started') return 'running';
  return latest.state;
}

function paramsOf(events: SimilarityStep[], step: SimilarityStepName): Record<string, unknown> {
  const latest = [...events].reverse().find((event) => event.step === step);
  return latest?.params ?? {};
}

function TraceRow({
  step,
  state,
  params,
}: {
  step: SimilarityStepName;
  state: RowState;
  params: Record<string, unknown>;
}) {
  const { t } = useTranslation();
  // `done` is the only state with counts to report; the others have a sentence
  // about themselves, because "0 candidates" for a rung that never ran is the
  // one thing this display must not say.
  const detailKey =
    state === 'done'
      ? `lifecycle.similarity.trace.detail.${step}`
      : `lifecycle.similarity.trace.state.${state}`;

  return (
    <li className="flex items-start gap-3">
      <span
        className={cn(
          'mt-0.5 grid size-7 shrink-0 place-items-center rounded-full border',
          TONE[state],
        )}
        aria-hidden
      >
        {ICONS[state]}
      </span>
      <div className="grid gap-0.5 pt-0.5">
        <span className={cn('text-caption font-semibold', state === 'pending' ? 'text-muted' : 'text-ink')}>
          {t(`lifecycle.similarity.trace.step.${step}`)}
        </span>
        <span className="text-caption leading-relaxed text-muted">{t(detailKey, params)}</span>
      </div>
    </li>
  );
}

export interface SimilarityTraceSheetProps {
  open: boolean;
  /** True while the run is still going. False once the answer has landed. */
  running: boolean;
  steps: SimilarityStep[];
  /** Set once the answer has landed: what the floor was, and what it removed. */
  matchFloor: number;
  belowFloor: number;
  shown: number;
  failed: boolean;
  onClose: () => void;
}

/**
 * The duplicate check, narrating itself while it runs.
 *
 * **Why this exists at all.** The funnel has been measured at up to twenty-five
 * seconds and used to spend all of them behind a button that said "checking".
 * Then either a dialog appeared with two prompts on it, or nothing appeared —
 * and *nothing* is now the ordinary outcome, because only a candidate covering
 * 90% of the incoming prompt is listed at all. A check that runs for twenty
 * seconds and then vanishes has told nobody anything, and "we found no
 * duplicates" is a claim, not an absence: it is worth exactly as much as the
 * search behind it, which until now was invisible.
 *
 * So the rungs report as they finish, with their real counts, and the last row
 * says how many candidates the floor removed. A person who thinks the answer is
 * wrong can see which rung to disbelieve.
 */
export function SimilarityTraceSheet({
  open,
  running,
  steps,
  matchFloor,
  belowFloor,
  shown,
  failed,
  onClose,
}: SimilarityTraceSheetProps) {
  const { t } = useTranslation();
  const floor = Math.round(matchFloor * 100);

  return (
    <BottomSheet
      open={open}
      onClose={onClose}
      title={t('lifecycle.similarity.trace.title')}
      description={t(running ? 'lifecycle.similarity.trace.subtitleRunning' : 'lifecycle.similarity.trace.subtitleDone')}
      footer={
        running ? (
          <p className="text-caption text-muted">{t('lifecycle.similarity.trace.waiting')}</p>
        ) : (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-caption text-muted">
              {failed
                ? t('lifecycle.similarity.trace.failed')
                : shown > 0
                  ? t('lifecycle.similarity.trace.foundSome', { shown, floor })
                  : t('lifecycle.similarity.trace.foundNone', { floor })}
            </p>
            <Button type="button" onClick={onClose} trailingIcon={<ArrowRight aria-hidden className="size-4" />}>
              {t('lifecycle.similarity.trace.continue')}
            </Button>
          </div>
        )
      }
    >
      <ol className="grid gap-4">
        {STEPS.map((step) => (
          <TraceRow key={step} step={step} state={rowState(steps, step)} params={paramsOf(steps, step)} />
        ))}
      </ol>
      {/* The floor, said on the screen that the floor is acting on. `below_floor`
          is the number that keeps "nothing found" honest: a row missing because
          of a threshold and a row nothing found look identical otherwise. */}
      {!running && belowFloor > 0 ? (
        <p className="mt-4 rounded-lg border border-border bg-subtle px-3 py-2 text-caption leading-relaxed text-muted">
          {t('lifecycle.similarity.trace.hidden', { hidden: belowFloor, floor })}
        </p>
      ) : null}
    </BottomSheet>
  );
}
