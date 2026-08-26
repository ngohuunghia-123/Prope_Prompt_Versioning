import { ArrowLeft, Check, PencilSimple } from '@phosphor-icons/react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Notification } from '@/components/Notification';
import { Button } from '@/components/ui/Button';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { declareUsageProfileAxis, getReadinessCard } from '@/features/prompt-lifecycle/readinessApi';
import { USAGE_PROFILE_AXES, type ReadinessCard, type UsageProfileAxis } from '@/features/prompt-lifecycle/readinessTypes';

const AXES: UsageProfileAxis[] = ['audience', 'untrusted_input', 'acts', 'sensitivity'];

interface UsageProfileWizardProps { promptId: string; versionId: string; }

export function UsageProfileWizard({ promptId, versionId }: UsageProfileWizardProps) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const queryKey = ['readiness', promptId, versionId, 'edit'];
  const query = useQuery({ queryKey, queryFn: () => getReadinessCard(promptId, versionId, 'edit'), staleTime: 15_000 });
  const [step, setStep] = useState<number>();
  const [sessionComplete, setSessionComplete] = useState(false);
  const profile = query.data?.profile;
  const firstUndeclared = profile ? AXES.findIndex((axis) => profile[axis] === 'undeclared') : 0;
  const activeStep = step ?? (firstUndeclared === -1 ? AXES.length : firstUndeclared);
  const complete = sessionComplete || activeStep >= AXES.length;
  const axis = AXES[Math.min(activeStep, AXES.length - 1)] ?? 'audience';

  const declaration = useMutation({
    mutationFn: ({ field, value }: { field: UsageProfileAxis; value: string }) => declareUsageProfileAxis(promptId, field, value),
    onSuccess: (_result, variables) => {
      client.setQueryData<ReadinessCard>(queryKey, (current) => current ? {
        ...current,
        profile: {
          ...current.profile,
          [variables.field]: variables.value,
          is_declared: AXES.every((field) => (field === variables.field ? variables.value : current.profile[field]) !== 'undeclared'),
        },
      } : current);
      const next = activeStep + 1;
      setStep(next);
      if (next >= AXES.length) setSessionComplete(true);
    },
  });

  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError || !profile) return <QueryState state="error" onRetry={() => void query.refetch()} />;

  return (
    <section aria-labelledby="usage-profile-title" className="overflow-hidden rounded-modal border border-border bg-surface shadow-panel">
      <div className="border-b border-border p-5">
        <p className="text-overline font-bold tracking-navigation-overline text-muted uppercase">{t('lifecycle.surface.monitoring.profile.eyebrow')}</p>
        <div className="mt-1 flex flex-wrap items-start justify-between gap-3">
          <div><h2 id="usage-profile-title" className="font-display text-heading-3 text-ink">{t('readiness.profile.title')}</h2><p className="mt-1 max-w-prose text-body text-muted">{t('lifecycle.surface.monitoring.profile.description')}</p></div>
          {complete ? <Button size="small" intent="ghost" leadingIcon={<PencilSimple aria-hidden className="size-4" />} onClick={() => { setSessionComplete(false); setStep(0); }}>{t('lifecycle.surface.monitoring.profile.edit')}</Button> : <span className="rounded-full bg-subtle px-3 py-1 text-caption font-semibold text-muted">{t('lifecycle.surface.monitoring.profile.progress', { current: activeStep + 1, total: AXES.length })}</span>}
        </div>
      </div>
      {complete ? (
        <dl className="grid gap-px bg-border sm:grid-cols-2">{AXES.map((field) => <div key={field} className="bg-surface p-4"><dt className="text-caption text-muted">{t(`readiness.profile.axis.${field}`)}</dt><dd className="mt-1 flex items-center gap-2 text-body font-semibold text-ink"><Check aria-hidden className="size-4 text-success" />{t(`readiness.profile.value.${profile[field]}`)}</dd></div>)}</dl>
      ) : (
        <div className="grid gap-4 p-5" aria-busy={declaration.isPending}>
          <div><p className="text-caption font-semibold text-muted">{t('lifecycle.surface.monitoring.profile.questionLabel', { current: activeStep + 1 })}</p><h3 className="mt-1 text-heading-3 text-ink">{t(`readiness.profile.axis.${axis}`)}</h3></div>
          <div className="grid gap-2 sm:grid-cols-2">{USAGE_PROFILE_AXES[axis].map((value) => <Button key={value} type="button" intent={profile[axis] === value ? 'secondary' : 'neutral'} className="min-h-12 justify-start whitespace-normal text-left" disabled={declaration.isPending} onClick={() => declaration.mutate({ field: axis, value })}>{t(`readiness.profile.value.${value}`)}</Button>)}</div>
          {declaration.isError ? <Notification tone="error" title={t('lifecycle.surface.monitoring.profile.saveError')}>{t('lifecycle.surface.monitoring.profile.saveErrorHint')}</Notification> : null}
          {activeStep > 0 ? <Button type="button" size="small" intent="ghost" className="w-fit" leadingIcon={<ArrowLeft aria-hidden className="size-4" />} onClick={() => setStep(activeStep - 1)}>{t('common.back')}</Button> : null}
        </div>
      )}
    </section>
  );
}
