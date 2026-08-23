import { ArrowCounterClockwise } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Notification } from '@/components/Notification';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import type { TrialSettings } from '@/features/prompt-lifecycle/components/useTrialChat';
import { providerConfigsOptions, providerModelsOptions } from '@/features/prompt-lifecycle/queries';
import type { TrialParameters } from '@/features/prompt-lifecycle/trialApi';
import type { Revision } from '@/features/prompt-lifecycle/types';

/** The five knobs the server accepts, with the bounds it enforces. One list, both sides. */
const CONTROLS = [
  { name: 'temperature', min: 0, max: 2, step: 0.1 },
  { name: 'top_p', min: 0.01, max: 1, step: 0.05 },
  { name: 'max_tokens', min: 1, max: 8192, step: 1 },
  { name: 'presence_penalty', min: -2, max: 2, step: 0.1 },
  { name: 'frequency_penalty', min: -2, max: 2, step: 0.1 },
] as const;

type ControlName = (typeof CONTROLS)[number]['name'];

interface PlaygroundSettingsProps {
  revisions: Revision[];
  versionId: string;
  onVersionChange: (versionId: string) => void;
  /** `{{variable}}` names the chosen revision's body demands. */
  neededVariables: string[];
  variables: Record<string, string>;
  onVariableChange: (name: string, value: string) => void;
  settings: TrialSettings;
  onSettingsChange: (settings: TrialSettings) => void;
  promptTitle: string;
  lockRevision?: boolean;
}

/**
 * Which revision, on which model, with which knobs.
 *
 * **Everything on this panel is scoped to the next turn and writes nothing.**
 * There is no save button because there is nothing to save: the revision keeps
 * the binding a reviewer approved, and an override travels on the request body of
 * one trial. That is the point of it — *would this be as good on the cheap model*
 * is a question worth an experiment and not worth two throwaway revisions on an
 * immutable chain.
 *
 * **A blank control means "as the revision has it", not "default".** The server
 * merges only the figures actually set (`exclude_none`), so clearing a box
 * restores the revision's own parameter rather than substituting a house default —
 * which would quietly make the trial a test of something else.
 */
export function PlaygroundSettings({
  revisions,
  versionId,
  onVersionChange,
  neededVariables,
  variables,
  onVariableChange,
  settings,
  onSettingsChange,
  promptTitle,
  lockRevision = false,
}: PlaygroundSettingsProps) {
  const { t } = useTranslation();
  const configsQuery = useQuery(providerConfigsOptions);
  const revision = revisions.find((item) => item.id === versionId);

  // The provider whose catalogue the model select shows: the override when one is
  // set, otherwise the revision's own, so opening the panel lists the models of
  // the configuration this revision already uses instead of an empty box.
  const activeProvider = settings.providerConfigId || revision?.providerConfigId || '';
  const modelsQuery = useQuery({
    ...providerModelsOptions(activeProvider),
    enabled: activeProvider !== '',
  });

  const configs = configsQuery.data ?? [];
  const models = modelsQuery.data ?? [];
  const overridden =
    settings.providerConfigId !== '' || Object.keys(settings.parameters).length > 0;

  function setParameter(name: ControlName, raw: string) {
    const next: TrialParameters = { ...settings.parameters };
    if (raw.trim() === '') {
      delete next[name];
    } else {
      const value = Number(raw);
      if (Number.isNaN(value)) return;
      next[name] = name === 'max_tokens' ? Math.round(value) : value;
    }
    onSettingsChange({ ...settings, parameters: next });
  }

  function chooseProvider(providerConfigId: string) {
    // Changing the provider clears the model: a model id is only meaningful
    // inside the catalogue it came from, and carrying one across would send a
    // binding that cannot resolve.
    onSettingsChange({ ...settings, providerConfigId, upstreamModel: '' });
  }

  const revisionOptions = revisions.map((item) => ({
    value: item.id,
    label: t('lifecycle.playground.revisionOption', {
      revision: item.number,
      status: t(`lifecycle.status.${item.status}`, { defaultValue: item.status }),
    }),
  }));

  const providerOptions = [
    { value: '', label: t('lifecycle.playground.settings.asRevision') },
    ...configs.map((config) => ({ value: config.provider_config_id, label: config.display_name })),
  ];

  const modelOptions = [
    { value: '', label: t('lifecycle.playground.settings.chooseModel') },
    ...models
      .filter((model) => model.available)
      .map((model) => ({ value: model.model_id, label: model.display_name || model.model_id })),
  ];

  const halfBound = settings.providerConfigId !== '' && settings.upstreamModel === '';

  return (
    <section className="grid gap-4 rounded-modal border border-border bg-subtle p-4" aria-labelledby="playground-settings-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 id="playground-settings-title" className="text-body font-semibold text-ink">
            {t('lifecycle.playground.settings.title')}
          </h3>
          <p className="mt-1 text-caption text-muted">{t('lifecycle.playground.settings.description')}</p>
        </div>
        {overridden ? (
          <Button
            type="button"
            intent="ghost"
            size="small"
            leadingIcon={<ArrowCounterClockwise aria-hidden className="size-4" />}
            onClick={() =>
              onSettingsChange({ providerConfigId: '', upstreamModel: '', parameters: {} })
            }
          >
            {t('lifecycle.playground.settings.reset')}
          </Button>
        ) : null}
      </div>

      <dl className="grid gap-3 rounded-lg border border-border bg-surface p-3 sm:grid-cols-2">
        <div className="min-w-0">
          <dt className="text-caption text-muted">{t('lifecycle.playground.promptLabel')}</dt>
          <dd className="truncate text-body font-medium text-ink">{promptTitle}</dd>
        </div>
        {revision ? (
          <div className="min-w-0">
            <dt className="text-caption text-muted">{t('lifecycle.playground.revisionLabel')}</dt>
            <dd className="truncate text-body font-medium text-ink">
              {t('lifecycle.playground.revisionOption', {
                revision: revision.number,
                status: t(`lifecycle.status.${revision.status}`, { defaultValue: revision.status }),
              })}
            </dd>
          </div>
        ) : null}
      </dl>

      {!lockRevision && revisionOptions.length > 0 ? (
        <Select
          label={t('lifecycle.playground.revisionLabel')}
          options={revisionOptions}
          value={versionId}
          onValueChange={onVersionChange}
        />
      ) : null}

      {neededVariables.length > 0 ? (
        <div className="grid gap-3 rounded-modal border border-dashed border-border bg-subtle p-4">
          <p className="text-caption text-muted">{t('lifecycle.playground.variablesHint')}</p>
          <div className="grid gap-3">
            {neededVariables.map((name) => (
              <Input
                key={name}
                label={name}
                value={variables[name] ?? ''}
                spellCheck={false}
                placeholder={t('lifecycle.playground.variablePlaceholder')}
                onChange={(event) => onVariableChange(name, event.target.value)}
              />
            ))}
          </div>
        </div>
      ) : null}

      <div className="grid gap-3">
        <Select
          label={t('lifecycle.playground.settings.providerLabel')}
          options={providerOptions}
          value={settings.providerConfigId}
          onValueChange={chooseProvider}
        />
        {settings.providerConfigId !== '' ? (
          <Select
            label={t('lifecycle.playground.settings.modelLabel')}
            options={modelOptions}
            value={settings.upstreamModel}
            disabled={modelsQuery.isPending}
            onValueChange={(upstreamModel) => onSettingsChange({ ...settings, upstreamModel })}
          />
        ) : (
          <p className="text-caption text-muted">
            {revision?.upstreamModel
              ? t('lifecycle.playground.settings.revisionModel', { model: revision.upstreamModel })
              : t('lifecycle.playground.settings.revisionUnbound')}
          </p>
        )}
      </div>

      {halfBound ? (
        <Notification tone="info" title={t('lifecycle.playground.settings.pickModel')}>
          {t('lifecycle.playground.settings.pickModelHint')}
        </Notification>
      ) : null}

      <details className="group rounded-lg border border-border bg-surface">
        <summary className="cursor-pointer list-none px-4 py-3 text-body font-medium text-ink focus-visible:outline-2 focus-visible:outline-focus">
          {t('lifecycle.playground.settings.advanced')}
        </summary>
        <fieldset className="grid gap-3 border-t border-border p-4">
          <legend className="sr-only">{t('lifecycle.playground.settings.parameters')}</legend>
          <div className="grid gap-3 sm:grid-cols-2">
            {CONTROLS.map((control) => {
              const inherited = revision?.parameters?.[control.name];
              return (
                <Input
                  key={control.name}
                  type="number"
                  inputMode="decimal"
                  min={control.min}
                  max={control.max}
                  step={control.step}
                  label={t(`lifecycle.playground.settings.control.${control.name}`)}
                  value={settings.parameters[control.name] ?? ''}
                  placeholder={
                    typeof inherited === 'number' || typeof inherited === 'string'
                      ? String(inherited)
                      : t('lifecycle.playground.settings.providerDefault')
                  }
                  onChange={(event) => setParameter(control.name, event.target.value)}
                />
              );
            })}
          </div>
          <p className="text-caption text-muted">{t('lifecycle.playground.settings.parametersHint')}</p>
        </fieldset>
      </details>

      {overridden ? (
        <Notification tone="info" title={t('lifecycle.playground.settings.overridden')}>
          {t('lifecycle.playground.settings.overriddenHint')}
        </Notification>
      ) : null}
    </section>
  );
}
