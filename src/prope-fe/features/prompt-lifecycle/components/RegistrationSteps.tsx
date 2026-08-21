import { ArrowLeft, Check } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/cn';

/**
 * The three screens registering a prompt actually passes through, named on the
 * screen you are standing on.
 *
 * `compose` is `/prompts/folder/:folderId/new`, `evaluate` is
 * `/prompts/:promptId/evaluation/run`, `publish` is the prompt's own page. They
 * were already a sequence — the composer navigates to evaluation on save — but
 * nothing said so, and nothing offered the way back, so somebody who reached
 * evaluation and found the prompt bound to the wrong provider had no move left
 * except starting again.
 *
 * **`backTo` is the whole point of the component and it is not a browser
 * back.** Going back a step means opening the editor on the revision that was
 * just written, and saving there appends a *new* revision — a revision is
 * immutable once written (A-021), so there is nothing to go back and change,
 * only something to supersede. `history.back()` would land on a composer whose
 * form state died with the navigation.
 *
 * Only the previous step is a link. A step further ahead has not happened and
 * would be a link to a page with nothing on it; a step further back is not
 * ambiguous but skipping to it silently discards the one in between.
 */
export type RegistrationStepId = 'compose' | 'evaluate' | 'publish';

const ORDER: RegistrationStepId[] = ['compose', 'evaluate', 'publish'];

export interface RegistrationStepsProps {
  current: RegistrationStepId;
  /** Where the previous step lives. Absent on the first step, and absent
   * whenever the previous step cannot be reopened. */
  backTo?: string;
  className?: string;
}

export function RegistrationSteps({ current, backTo, className }: RegistrationStepsProps) {
  const { t } = useTranslation();
  const currentIndex = ORDER.indexOf(current);

  return (
    <nav
      aria-label={t('lifecycle.registration.label')}
      className={cn(
        'flex flex-wrap items-center gap-x-3 gap-y-2 rounded-modal border border-border bg-surface px-4 py-2.5 shadow-panel',
        className,
      )}
    >
      {backTo ? (
        <Link
          to={backTo}
          className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-caption font-medium text-link underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-focus"
        >
          <ArrowLeft aria-hidden className="size-4" weight="bold" />
          {t('lifecycle.registration.back', { step: t(`lifecycle.registration.steps.${ORDER[currentIndex - 1]}`) })}
        </Link>
      ) : null}

      <ol className="m-0 flex flex-wrap items-center gap-x-2 gap-y-1 p-0">
        {ORDER.map((step, index) => (
          <li
            key={step}
            aria-current={index === currentIndex ? 'step' : undefined}
            className={cn(
              'flex list-none items-center gap-1.5 rounded-full px-2.5 py-0.5 text-caption',
              index === currentIndex && 'bg-secondary font-medium text-inverse',
              index < currentIndex && 'text-muted',
              index > currentIndex && 'text-muted/70',
            )}
          >
            {index < currentIndex ? (
              <Check aria-hidden className="size-3.5" weight="bold" />
            ) : (
              <span aria-hidden className="font-mono">{index + 1}</span>
            )}
            {t(`lifecycle.registration.steps.${step}`)}
          </li>
        ))}
      </ol>
    </nav>
  );
}
