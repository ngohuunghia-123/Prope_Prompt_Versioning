import { Check } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/cn';

/**
 * The two screens of the authoring flow, named on the screen you are standing
 * on: `compose` (`/prompts/:promptId/edit`, or the folder's new-prompt route)
 * and `evaluate` (`/prompts/:promptId/evaluation/run`).
 *
 * **Every step with a known destination is a direct link — no step gates
 * another.** A revision is immutable once written (A-021), so moving between
 * steps never loses work: saving appends a new revision rather than changing
 * one, which is what makes jumping back to compose safe at any point. A step
 * whose destination does not exist yet — evaluation of an unsaved prompt —
 * stays a label until saving gives it somewhere to go.
 */
export type RegistrationStepId = 'compose' | 'evaluate';

const ORDER: RegistrationStepId[] = ['compose', 'evaluate'];

export interface RegistrationStepsProps {
  current: RegistrationStepId;
  /** Where each step lives. Absent for the current step, and for steps that
   * cannot exist yet (e.g. evaluation before the first save). */
  targets?: Partial<Record<RegistrationStepId, string>>;
  className?: string;
}

export function RegistrationSteps({ current, targets, className }: RegistrationStepsProps) {
  const { t } = useTranslation();
  const currentIndex = ORDER.indexOf(current);

  return (
    <nav
      aria-label={t('lifecycle.registration.label')}
      className={cn(
        'flex flex-wrap items-center gap-x-2 gap-y-1 rounded-modal border border-border bg-surface px-4 py-2.5 shadow-panel',
        className,
      )}
    >
      <ol className="m-0 flex flex-wrap items-center gap-x-2 gap-y-1 p-0">
        {ORDER.map((step, index) => {
          const target = index === currentIndex ? undefined : targets?.[step];
          const label = t(`lifecycle.registration.steps.${step}`);
          return (
            <li
              key={step}
              aria-current={index === currentIndex ? 'step' : undefined}
              className="flex list-none items-center"
            >
              {index > 0 ? (
                <span aria-hidden className="mx-2 text-muted/60">/</span>
              ) : null}
              {target ? (
                <Link
                  to={target}
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-caption font-medium text-link underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-focus',
                  )}
                >
                  {index < currentIndex ? (
                    <Check aria-hidden className="size-3.5" weight="bold" />
                  ) : (
                    <span aria-hidden className="font-mono">{index + 1}</span>
                  )}
                  {label}
                </Link>
              ) : (
                <span
                  className={cn(
                    'flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-caption',
                    index === currentIndex ? 'bg-secondary font-medium text-inverse' : 'text-muted/70',
                  )}
                >
                  {index < currentIndex ? (
                    <Check aria-hidden className="size-3.5" weight="bold" />
                  ) : (
                    <span aria-hidden className="font-mono">{index + 1}</span>
                  )}
                  {label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
