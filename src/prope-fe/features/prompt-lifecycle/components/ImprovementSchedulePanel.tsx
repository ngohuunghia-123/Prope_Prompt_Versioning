import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';

import { Button, Checkbox, Select } from '@/components/ui';
import { readSchedule, writeSchedule } from '@/features/prompt-lifecycle/improvementApi';
import { lifecycleKeys } from '@/features/prompt-lifecycle/queries';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';

/**
 * The re-probe cadence, INT-050 — the screen the setting never had.
 *
 * **The route existed and nothing rendered it.** `improvement.schedule.enabled`
 * defaults to false, so the only way to turn the weekly re-probe on was to PUT
 * the API by hand — which meant `probe_leak_appeared`, the detector that needs
 * two probe runs on one version, could not fire in the product at all. That is
 * the detector ADR-0068 calls the reason the opt-in re-probe is worth its money.
 *
 * **It lives on the inbox rather than on a settings page.** This is where a
 * person is when they think *is this everything Prope is watching for?*, and the
 * answer — *no, there is a deeper check and it costs money* — belongs in front
 * of that question rather than three clicks away from it.
 *
 * **No estimated figure, deliberately.** The catalogue used to carry an
 * `estimate` key and nothing computed one; there is no price-times-cases
 * estimator anywhere in the product. A number invented on the client for a
 * recurring charge on somebody else's provider account is worse than no number,
 * so the copy says what it does know: the cycle spends workspace credit, it
 * repeats, and the spend ceiling is the thing that actually stops it. That
 * follows `readiness.probe.cost`, which makes the same qualitative claim for the
 * one-off probe.
 *
 * **`spend_ceiling.manage` on both the read and the write**, so a person without
 * it gets a refusal from the query and this panel simply does not render. The
 * SPA carries no permission model — the route is the authority — which is why
 * there is no client-side check here and must not be one.
 */

/** 1..90, bounded by `ck_improvement_schedule_cadence_is_bounded` and the schema. */
const CADENCE_CHOICES = ['1', '7', '14', '30', '90'];

export function ImprovementSchedulePanel({ workspaceId }: { workspaceId: string }) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const client = useQueryClient();

  const query = useQuery({
    queryKey: lifecycleKeys.improvementSchedule(workspaceId),
    queryFn: () => readSchedule(workspaceId),
    staleTime: 60_000,
    retry: false,
  });

  const [enabled, setEnabled] = useState(false);
  const [cadence, setCadence] = useState('7');

  // The server's answer is the initial value, not a controlled binding — a person
  // mid-edit must not have their choice replaced by a background refetch.
  useEffect(() => {
    if (!query.data) return;
    setEnabled(query.data.enabled);
    setCadence(String(query.data.cadence_days));
  }, [query.data]);

  const save = useMutation({
    mutationFn: () =>
      writeSchedule(workspaceId, {
        enabled,
        cadence_days: Number(cadence),
        // Scope editing is not offered here. Empty arrays mean *every released
        // prompt*, which is what this control turns on; narrowing to namespaces
        // or ids is a separate decision with its own screen to earn, and
        // silently sending [] would erase a narrower scope somebody had set.
        namespaces: query.data?.namespaces ?? [],
        prompt_ids: query.data?.prompt_ids ?? [],
      }),
    onSuccess: (row) => {
      client.setQueryData(lifecycleKeys.improvementSchedule(workspaceId), row);
    },
  });

  // A refusal is the expected answer for a reader without `spend_ceiling.manage`,
  // and a spending control they cannot use is noise on their screen.
  if (query.isPending || query.isError || !query.data) return null;

  const schedule = query.data;
  const scoped = schedule.namespaces.length + schedule.prompt_ids.length > 0;
  const dirty = enabled !== schedule.enabled || Number(cadence) !== schedule.cadence_days;

  return (
    <section className="bg-surface p-4 sm:p-6">
      <h2 className="text-sm font-medium text-fg">{t('improvement.schedule.title')}</h2>
      <p className="mt-1 text-sm text-fg-muted">{t('improvement.schedule.description')}</p>

      <div className="mt-4 flex flex-wrap items-end gap-4">
        <Checkbox
          label={t('improvement.schedule.enabled')}
          checked={enabled}
          onChange={(event) => setEnabled(event.target.checked)}
        />
        <Select
          label={t('improvement.schedule.cadence')}
          options={CADENCE_CHOICES.map((value) => ({ value, label: value }))}
          value={cadence}
          onValueChange={setCadence}
          disabled={!enabled}
          className="w-32"
        />
        <Button
          size="small"
          disabled={!dirty || save.isPending}
          onClick={() => save.mutate()}
        >
          {save.isPending ? t('improvement.schedule.saving') : t('improvement.schedule.save')}
        </Button>
      </div>

      <p className="mt-3 text-xs text-fg-muted">
        {scoped
          ? t('improvement.schedule.scopeSome', {
              namespaces: schedule.namespaces.length,
              prompts: schedule.prompt_ids.length,
            })
          : t('improvement.schedule.scopeAll')}
        {' · '}
        {schedule.last_run_at
          ? t('improvement.schedule.lastRun', { when: format.date(schedule.last_run_at) })
          : t('improvement.schedule.never')}
      </p>

      {/*
        The charge, before the toggle is worth anything and regardless of its
        state. A recurring spend on the workspace's own credential is the one
        fact somebody must not discover from an invoice.
      */}
      <p className="mt-2 text-xs text-fg-muted">{t('improvement.schedule.cost')}</p>
      <p className="mt-1 text-xs text-fg-muted">{t('improvement.schedule.costHint')}</p>

      {/*
        A refusal here is most likely `spend_ceiling.manage` missing, and the copy
        says so rather than printing a server sentence — ADR-0053 puts every
        sentence on this side.
      */}
      {save.isError ? (
        <p className="mt-3 text-xs text-danger-text">{t('improvement.schedule.failed')}</p>
      ) : null}
      {save.isSuccess && !dirty ? (
        <p className="mt-3 text-xs text-success-text">{t('improvement.schedule.saved')}</p>
      ) : null}
    </section>
  );
}
