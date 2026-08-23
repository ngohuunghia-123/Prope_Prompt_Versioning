import { useTranslation } from 'react-i18next';

import { Select } from '@/components/ui';
import { Tag } from '@/components/Tag';
import { cn } from '@/lib/cn';
import {
  USAGE_PROFILE_AXES,
  type UsageProfile,
  type UsageProfileAxis,
} from '@/features/prompt-lifecycle/readinessTypes';

/**
 * The four dropdowns that decide what the readiness card tells you.
 *
 * **This is the whole differentiator, rendered as four selects.** Every
 * competitor lints context-free; the reason an internal-only prompt is never
 * told it lacks a public-facing guardrail is that somebody answered these four
 * questions once. The copy asks them as questions rather than labelling them as
 * fields, because *"Who can reach this prompt?"* gets an answer and
 * *"Audience"* gets a shrug.
 *
 * **Nothing here infers anything** (A-163). There is no *suggest* button and no
 * value derived from the body: a model guessing that a prompt is customer-facing
 * and then lecturing about it is the false positive this whole feature exists to
 * avoid, so inference here would be the bug rather than the missing feature.
 *
 * `undeclared` is a real option and not an empty state. Choosing it is somebody
 * withdrawing a declaration, which is a thing they may legitimately want to do,
 * and it puts the prompt back behind the worst-case badge where it can be seen.
 */

export interface UsageProfileFieldsProps {
  profile: UsageProfile;
  onChange: (axis: UsageProfileAxis, value: string) => void;
  disabled?: boolean;
  className?: string;
}

const AXES: UsageProfileAxis[] = ['audience', 'untrusted_input', 'acts', 'sensitivity'];

export function UsageProfileFields({
  profile,
  onChange,
  disabled = false,
  className,
}: UsageProfileFieldsProps) {
  const { t } = useTranslation();

  return (
    <section className={cn('space-y-4', className)}>
      <header className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-display text-heading-3 text-ink">{t('readiness.profile.title')}</h3>
          {profile.is_declared ? null : (
            <Tag state="warning">{t('readiness.profile.undeclaredBadge')}</Tag>
          )}
        </div>
        <p className="text-caption text-muted">{t('readiness.profile.description')}</p>
        {profile.is_declared ? null : (
          <p className="text-caption text-muted">{t('readiness.profile.undeclaredHint')}</p>
        )}
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        {AXES.map((axis) => {
          const current = profile[axis];
          const assumed = profile.assumed[axis];
          return (
            <div key={axis} className="space-y-1">
              <Select
                label={t(`readiness.profile.axis.${axis}`)}
                value={current}
                disabled={disabled}
                onValueChange={(value) => onChange(axis, value)}
                options={USAGE_PROFILE_AXES[axis].map((value) => ({
                  value,
                  label: t(`readiness.profile.value.${value}`),
                }))}
              />
              {/*
                Shown only where the axis is undeclared AND the assumption differs
                from what is selected — which is every undeclared axis. It says
                out loud what the rules are running against, so the conservative
                default is a visible assumption rather than a silent assertion
                that somebody called this prompt public.
              */}
              {current === 'undeclared' && assumed ? (
                <p className="text-caption text-muted">
                  {t('readiness.profile.assumedAs', {
                    value: t(`readiness.profile.value.${assumed}`),
                  })}
                </p>
              ) : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}
