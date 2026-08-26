import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { useFormContext } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router-dom';
import { Select } from '@/components/ui/Select';
import { providerConfigsOptions, providerModelsOptions } from '@/features/prompt-lifecycle/queries';
import type { PromptEditorValues } from '@/features/prompt-lifecycle/types';
import { cn } from '@/lib/cn';

const UNSET = '';
const PROVIDER_HIGHLIGHT_DURATION_MS = 1600;

/**
 * Which provider configuration and which upstream model this revision binds to.
 *
 * Both come from `provider_access` — the configurations the workspace actually
 * registered, and the model catalogue of whichever one is selected. What was
 * here before was a two-option vendor list and a free-text model box that were
 * never sent anywhere.
 *
 * The pair moves together, because the database refuses a half-binding
 * (`ck_revision_binding_is_whole`) and the schema mirrors that. Clearing the
 * provider clears the model rather than leaving a model pointing at nothing, and
 * changing the provider clears it too: a model id is only meaningful against the
 * configuration that serves it.
 */
export function ProviderBindingFields() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const form = useFormContext<PromptEditorValues>();
  const sectionRef = useRef<HTMLDivElement>(null);
  const providerConfigId = form.watch('providerConfigId');
  const upstreamModel = form.watch('upstreamModel');
  const focusedFromEvaluation = searchParams.get('focus') === 'provider-binding';
  const [highlighted, setHighlighted] = useState(false);

  const configs = useQuery(providerConfigsOptions);
  const models = useQuery({
    ...providerModelsOptions(providerConfigId),
    enabled: providerConfigId !== UNSET,
  });

  const providers = configs.data ?? [];
  const catalogue = models.data ?? [];

  useEffect(() => {
    if (!focusedFromEvaluation || configs.isPending) return;
    setHighlighted(true);
    sectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    sectionRef.current?.querySelector<HTMLButtonElement>('#provider-config-select')?.focus();
    const timeoutId = window.setTimeout(() => setHighlighted(false), PROVIDER_HIGHLIGHT_DURATION_MS);
    return () => window.clearTimeout(timeoutId);
  }, [configs.isPending, focusedFromEvaluation]);

  const chooseProvider = (value: string) => {
    form.setValue('providerConfigId', value, { shouldDirty: true, shouldValidate: true });
    form.setValue('upstreamModel', UNSET, { shouldDirty: true, shouldValidate: true });
  };

  const providerOptions = [
    { value: UNSET, label: t('lifecycle.editor.providerUnset') },
    ...providers.map((provider) => ({
      value: provider.provider_config_id,
      // A configuration that has not passed its probe is still selectable — it
      // may be waiting on a first verification — but the label says so, because
      // binding to one is binding to something that has not answered yet.
      label: provider.verification_status === 'passed'
        ? provider.display_name
        : t('lifecycle.editor.providerUnverified', { name: provider.display_name }),
    })),
  ];

  const modelOptions = [
    { value: UNSET, label: t('lifecycle.editor.modelUnset') },
    ...catalogue.map((model) => ({ value: model.model_id, label: model.display_name || model.model_id })),
  ];

  return (
    <div
      ref={sectionRef}
      className={cn(
        'grid gap-4 rounded-control transition-shadow duration-(--prope-motion-duration-slow) motion-reduce:transition-none',
        highlighted && 'ring-2 ring-secondary ring-offset-4 ring-offset-surface',
      )}
    >
      <Select
        id="provider-config-select"
        label={t('lifecycle.editor.provider')}
        options={providerOptions}
        value={providerConfigId}
        disabled={configs.isPending || configs.isError}
        onValueChange={chooseProvider}
      />

      {configs.isPending ? (
        <p role="status" className="text-caption text-muted">{t('lifecycle.editor.providersLoading')}</p>
      ) : null}

      {configs.isError ? (
        <p role="alert" className="text-caption text-danger-text">
          {t('lifecycle.editor.providersLoadError')}{' '}
          <button type="button" className="font-semibold underline focus-visible:outline-2 focus-visible:outline-focus" onClick={() => void configs.refetch()}>
            {t('lifecycle.editor.retry')}
          </button>
        </p>
      ) : null}

      {/* An empty catalogue is not the same as no provider selected: it means
          the configuration serves nothing this workspace has discovered yet, and
          the fix is on the provider page, not here.

          The error is rendered here because `superRefine` puts the half-binding
          issue on `upstreamModel`, and until now nothing displayed it: picking a
          provider and stopping left the form permanently invalid while both
          selects looked answered, and the submit button did nothing. */}
      <Select
        label={t('lifecycle.editor.providerModel')}
        options={modelOptions}
        value={upstreamModel}
        error={form.formState.errors.upstreamModel ? t('lifecycle.editor.providerModelIncomplete') : undefined}
        disabled={providerConfigId === UNSET || models.isPending || models.isError || catalogue.length === 0}
        onValueChange={(value) => form.setValue('upstreamModel', value, { shouldDirty: true, shouldValidate: true })}
      />

      {providerConfigId !== UNSET && models.isPending ? (
        <p role="status" className="text-caption text-muted">{t('lifecycle.editor.modelsLoading')}</p>
      ) : null}

      {providerConfigId !== UNSET && models.isError ? (
        <p role="alert" className="text-caption text-danger-text">
          {t('lifecycle.editor.modelsLoadError')}{' '}
          <button type="button" className="font-semibold underline focus-visible:outline-2 focus-visible:outline-focus" onClick={() => void models.refetch()}>
            {t('lifecycle.editor.retry')}
          </button>
        </p>
      ) : null}

      {providers.length === 0 && !configs.isPending && !configs.isError ? (
        <p className="text-caption text-muted">
          {t('lifecycle.editor.noProviders')}{' '}
          <Link to="/app/providers" className="text-link underline focus-visible:outline-2 focus-visible:outline-focus">
            {t('lifecycle.editor.registerProvider')}
          </Link>
        </p>
      ) : null}

      {providerConfigId !== UNSET && catalogue.length === 0 && !models.isPending && !models.isError ? (
        <p className="text-caption text-muted">{t('lifecycle.editor.noModels')}</p>
      ) : null}
    </div>
  );
}
