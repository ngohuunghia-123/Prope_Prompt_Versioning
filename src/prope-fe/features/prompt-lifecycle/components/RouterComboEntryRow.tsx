import { ArrowDown, ArrowUp, Trash } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { providerModelsOptions } from '@/features/prompt-lifecycle/queries';
import type { ProviderRead } from '@/features/prompt-lifecycle/providerTypes';
import type { RouterComboEntryInput } from '@/features/prompt-lifecycle/routerComboTypes';

const UNSET = '';

/**
 * One rung of a combo, as the dialog edits it — ADR-0069.
 *
 * **This has to be its own component.** Each rung needs its own
 * `useQuery(providerModelsOptions(...))` against whichever provider it names,
 * and hooks cannot run inside a `.map()`. The obvious inline version does not
 * compile, and the version that "fixes" it by fetching every catalogue up front
 * makes N requests on open for a list the user may not touch.
 *
 * Ordering is the array index and nothing else. The up/down buttons move the
 * row; `priority` is derived at send time. A number field would admit
 * duplicates and gaps — two validations for a fact the array already carries —
 * and there is no drag dependency in this app to reach for instead.
 */
export function RouterComboEntryRow({
  index,
  total,
  entry,
  providers,
  duplicate,
  onChange,
  onMove,
  onRemove,
}: {
  index: number;
  total: number;
  entry: RouterComboEntryInput;
  providers: readonly ProviderRead[];
  /** This rung repeats an earlier `(provider, model)` pair — the server refuses it. */
  duplicate: boolean;
  onChange: (next: RouterComboEntryInput) => void;
  onMove: (direction: -1 | 1) => void;
  onRemove: () => void;
}) {
  const { t } = useTranslation();
  const models = useQuery({
    ...providerModelsOptions(entry.providerConfigId),
    enabled: entry.providerConfigId !== UNSET,
  });
  const catalogue = models.data ?? [];

  const providerOptions = [
    { value: UNSET, label: t('lifecycle.editor.providerUnset') },
    ...providers.map((provider) => ({
      value: provider.provider_config_id,
      // A disabled or unverified provider stays **selectable**: a combo is a
      // template that outlives today's verification state, and the rung a
      // workspace most wants is often the one it has not finished setting up.
      // The label says so, and the saved card warns, which is the difference
      // between an informed choice and a first rung that silently degrades.
      label: provider.verification_status === 'passed' && provider.status === 'active'
        ? provider.display_name
        : t('lifecycle.editor.providerUnverified', { name: provider.display_name }),
    })),
  ];

  const modelOptions = [
    { value: UNSET, label: t('lifecycle.editor.modelUnset') },
    ...catalogue.map((model) => ({ value: model.model_id, label: model.display_name || model.model_id })),
  ];

  return (
    <li className="grid gap-3 rounded-control border border-border bg-subtle p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-caption font-medium text-ink">
          {index === 0
            ? t('lifecycle.router.dialog.entryPrimary', { rank: index + 1 })
            : t('lifecycle.router.priority', { rank: index + 1 })}
        </span>
        <div className="flex items-center gap-1">
          <Button
            type="button"
            intent="neutral"
            size="icon"
            aria-label={t('lifecycle.router.dialog.moveUp', { rank: index + 1 })}
            disabled={index === 0}
            onClick={() => onMove(-1)}
          >
            <ArrowUp aria-hidden className="size-4" />
          </Button>
          <Button
            type="button"
            intent="neutral"
            size="icon"
            aria-label={t('lifecycle.router.dialog.moveDown', { rank: index + 1 })}
            disabled={index === total - 1}
            onClick={() => onMove(1)}
          >
            <ArrowDown aria-hidden className="size-4" />
          </Button>
          <Button
            type="button"
            intent="neutral"
            size="icon"
            aria-label={t('lifecycle.router.dialog.removeEntry', { rank: index + 1 })}
            onClick={onRemove}
          >
            <Trash aria-hidden className="size-4" />
          </Button>
        </div>
      </div>

      <Select
        label={t('lifecycle.editor.provider')}
        options={providerOptions}
        value={entry.providerConfigId}
        // Changing the provider clears the model: a model id is only meaningful
        // against the configuration that serves it. Same rule the single
        // binding already keeps.
        onValueChange={(value) => onChange({ providerConfigId: value, upstreamModel: UNSET })}
      />

      <Select
        label={t('lifecycle.editor.providerModel')}
        options={modelOptions}
        value={entry.upstreamModel}
        error={duplicate ? t('lifecycle.router.dialog.duplicateEntry') : undefined}
        disabled={entry.providerConfigId === UNSET || models.isPending || models.isError || catalogue.length === 0}
        onValueChange={(value) => onChange({ ...entry, upstreamModel: value })}
      />

      {entry.providerConfigId !== UNSET && models.isPending ? (
        <p role="status" className="text-caption text-muted">{t('lifecycle.editor.modelsLoading')}</p>
      ) : null}

      {entry.providerConfigId !== UNSET && models.isError ? (
        <p role="alert" className="text-caption text-danger-text">
          {t('lifecycle.editor.modelsLoadError')}{' '}
          <button
            type="button"
            className="font-semibold underline focus-visible:outline-2 focus-visible:outline-focus"
            onClick={() => void models.refetch()}
          >
            {t('lifecycle.editor.retry')}
          </button>
        </p>
      ) : null}

      {entry.providerConfigId !== UNSET && catalogue.length === 0 && !models.isPending && !models.isError ? (
        <p className="text-caption text-muted">{t('lifecycle.editor.noModels')}</p>
      ) : null}
    </li>
  );
}
