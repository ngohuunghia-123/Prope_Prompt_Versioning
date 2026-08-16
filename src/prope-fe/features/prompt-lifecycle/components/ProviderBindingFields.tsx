import { useQuery } from '@tanstack/react-query';
import { useFormContext } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Select } from '@/components/ui/Select';
import { providerConfigsOptions, providerModelsOptions } from '@/features/prompt-lifecycle/queries';
import type { PromptEditorValues } from '@/features/prompt-lifecycle/types';

const UNSET = '';

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
  const form = useFormContext<PromptEditorValues>();
  const providerConfigId = form.watch('providerConfigId');
  const upstreamModel = form.watch('upstreamModel');

  const configs = useQuery(providerConfigsOptions);
  const models = useQuery({
    ...providerModelsOptions(providerConfigId),
    enabled: providerConfigId !== UNSET,
  });

  const providers = configs.data ?? [];
  const catalogue = models.data ?? [];

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
    <>
      <Select
        label={t('lifecycle.editor.provider')}
        options={providerOptions}
        value={providerConfigId}
        onValueChange={chooseProvider}
      />

      {/* An empty catalogue is not the same as no provider selected: it means
          the configuration serves nothing this workspace has discovered yet, and
          the fix is on the provider page, not here. */}
      <Select
        label={t('lifecycle.editor.providerModel')}
        options={modelOptions}
        value={upstreamModel}
        disabled={providerConfigId === UNSET || catalogue.length === 0}
        onValueChange={(value) => form.setValue('upstreamModel', value, { shouldDirty: true, shouldValidate: true })}
      />

      {providers.length === 0 && !configs.isPending ? (
        <p className="text-caption text-muted">
          {t('lifecycle.editor.noProviders')}{' '}
          <Link to="/app/providers" className="text-link underline focus-visible:outline-2 focus-visible:outline-focus">
            {t('lifecycle.editor.registerProvider')}
          </Link>
        </p>
      ) : null}

      {providerConfigId !== UNSET && catalogue.length === 0 && !models.isPending ? (
        <p className="text-caption text-muted">{t('lifecycle.editor.noModels')}</p>
      ) : null}
    </>
  );
}
