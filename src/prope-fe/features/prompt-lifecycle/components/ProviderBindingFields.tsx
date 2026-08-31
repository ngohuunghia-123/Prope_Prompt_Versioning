import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useFormContext } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { SegmentedControl } from '@/components/SegmentedControl';
import { Select } from '@/components/ui/Select';
import { RouterComboDialog } from '@/features/prompt-lifecycle/components/RouterComboDialog';
import { RouterComboSummary } from '@/features/prompt-lifecycle/components/RouterComboSummary';
import { readLastProviderBinding } from '@/features/prompt-lifecycle/providerBindingMemory';
import type { ProviderModel, ProviderRead } from '@/features/prompt-lifecycle/providerTypes';
import {
  providerConfigsOptions,
  providerModelsOptions,
  routerCombosOptions,
} from '@/features/prompt-lifecycle/queries';
import { readLastRouterCombo } from '@/features/prompt-lifecycle/routerComboMemory';
import type { RouterCombo } from '@/features/prompt-lifecycle/routerComboTypes';
import type { PromptEditorValues } from '@/features/prompt-lifecycle/types';
import { cn } from '@/lib/cn';

const UNSET = '';
const PROVIDER_HIGHLIGHT_DURATION_MS = 1600;

/**
 * One provider and one model — today's binding, moved verbatim.
 *
 * The pair moves together, because the database refuses a half-binding
 * (`ck_revision_binding_is_whole`) and the schema mirrors that. Clearing the
 * provider clears the model rather than leaving a model pointing at nothing, and
 * changing the provider clears it too: a model id is only meaningful against the
 * configuration that serves it.
 */
function SingleBindingFields({ providers, catalogue, configs, models }: {
  providers: readonly ProviderRead[];
  catalogue: readonly ProviderModel[];
  configs: ReturnType<typeof useQuery<ProviderRead[]>>;
  models: ReturnType<typeof useQuery<ProviderModel[]>>;
}) {
  const { t } = useTranslation();
  const form = useFormContext<PromptEditorValues>();
  const providerConfigId = form.watch('providerConfigId');
  const upstreamModel = form.watch('upstreamModel');

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
        searchable
        searchPlaceholder={t('lifecycle.editor.modelSearchPlaceholder')}
        noMatchesLabel={t('lifecycle.editor.modelSearchEmpty')}
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
          {/* Straight to the settings destination rather than through
              `/app/providers`, which is a redirect route. */}
          <Link to="/app/settings/providers" className="text-link underline focus-visible:outline-2 focus-visible:outline-focus">
            {t('lifecycle.editor.registerProvider')}
          </Link>
        </p>
      ) : null}

      {providerConfigId !== UNSET && catalogue.length === 0 && !models.isPending && !models.isError ? (
        <p className="text-caption text-muted">{t('lifecycle.editor.noModels')}</p>
      ) : null}
    </>
  );
}

/**
 * One router combo, copied into this revision frozen — ADR-0069.
 *
 * The rungs are rendered under the select rather than inside its options:
 * `SelectOption` is flat `{value,label}`, and a combo's NAME tells an author
 * nothing about what they are choosing. What matters is `1. OpenAI · gpt-4o-mini
 * → 2. Azure · gpt-4o`.
 *
 * **"Create new combo" opens a dialog here; it does not navigate.** The draft
 * autosave runs only on the create path, so a link out of the *edit* composer
 * loses the edit outright — and even on create, the 600 ms debounce can lose the
 * last word somebody typed.
 */
function ComboBindingField({ combos, comboQuery }: {
  combos: readonly RouterCombo[];
  comboQuery: ReturnType<typeof useQuery<RouterCombo[]>>;
}) {
  const { t } = useTranslation();
  const form = useFormContext<PromptEditorValues>();
  const routeComboId = form.watch('routeComboId');
  const [creating, setCreating] = useState(false);

  const selected = combos.find((combo) => combo.combo_id === routeComboId);

  const comboOptions = [
    { value: UNSET, label: t('lifecycle.editor.comboUnset') },
    ...combos.map((combo) => ({ value: combo.combo_id, label: combo.display_name })),
  ];

  return (
    <>
      <Select
        id="router-combo-select"
        label={t('lifecycle.editor.combo')}
        options={comboOptions}
        value={routeComboId}
        error={form.formState.errors.routeComboId ? t('lifecycle.editor.comboRequired') : undefined}
        disabled={comboQuery.isPending || comboQuery.isError || combos.length === 0}
        onValueChange={(value) => form.setValue('routeComboId', value, { shouldDirty: true, shouldValidate: true })}
      />

      {selected ? <RouterComboSummary entries={selected.entries} /> : null}

      {comboQuery.isPending ? (
        <p role="status" className="text-caption text-muted">{t('lifecycle.editor.combosLoading')}</p>
      ) : null}

      {comboQuery.isError ? (
        <p role="alert" className="text-caption text-danger-text">
          {t('lifecycle.editor.combosLoadError')}{' '}
          <button type="button" className="font-semibold underline focus-visible:outline-2 focus-visible:outline-focus" onClick={() => void comboQuery.refetch()}>
            {t('lifecycle.editor.retry')}
          </button>
        </p>
      ) : null}

      {combos.length === 0 && !comboQuery.isPending && !comboQuery.isError ? (
        <p className="text-caption text-muted">{t('lifecycle.editor.noCombos')}</p>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" intent="neutral" size="small" onClick={() => setCreating(true)}>
          {t('lifecycle.editor.createCombo')}
        </Button>
        <Link to="/app/settings/router" className="text-caption text-link underline focus-visible:outline-2 focus-visible:outline-focus">
          {t('lifecycle.editor.manageCombos')}
        </Link>
      </div>

      {/* The rule this screen is the one place somebody meets it: what gets
          stored is a COPY. Editing the combo afterwards changes what the next
          revision copies and nothing that is already released. */}
      <p className="rounded-control bg-subtle px-3 py-2 text-caption text-muted">
        {t('lifecycle.editor.comboSnapshotHint')}
      </p>

      <RouterComboDialog
        open={creating}
        onClose={() => setCreating(false)}
        onSaved={(combo) => form.setValue('routeComboId', combo.combo_id, { shouldDirty: true, shouldValidate: true })}
      />
    </>
  );
}

/**
 * What this revision binds to: one provider and model, or one router combo.
 *
 * A-024 makes both part of the revision — the caller cannot override either —
 * and ADR-0069 makes them exclusive at the database: a revision carries a pair
 * or a route, never both. The switch is a mode rather than an inference from
 * which field is filled, so flipping back and forth does not destroy the other
 * choice; exclusivity is applied at the send site, where the server can trust it.
 *
 * Both memory restores live in this shell and not in the children, and that is
 * structural rather than tidy: restoring a remembered combo has to SET THE MODE,
 * and a component that only mounts in combo mode cannot switch the form into it.
 */
export function ProviderBindingFields() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const form = useFormContext<PromptEditorValues>();
  const sectionRef = useRef<HTMLDivElement>(null);
  const bindingMode = form.watch('bindingMode');
  const providerConfigId = form.watch('providerConfigId');
  const focusedFromEvaluation = searchParams.get('focus') === 'provider-binding';
  const [highlighted, setHighlighted] = useState(false);

  // The remembered model, held between the two effects below. It cannot be
  // written at the same time as the provider: the catalogue it has to be checked
  // against is fetched FOR that provider, so it does not exist yet at the moment
  // the provider is chosen.
  const rememberedModel = useRef<string | undefined>(undefined);
  const prefilled = useRef(false);

  const configs = useQuery(providerConfigsOptions);
  const comboQuery = useQuery(routerCombosOptions);
  const models = useQuery({
    ...providerModelsOptions(providerConfigId),
    enabled: providerConfigId !== UNSET,
  });

  // Memoised because both are read by effects below, and `?? []` hands back a
  // fresh array on every render while the query is still pending — which would
  // re-run those effects on every render rather than when the data changes.
  const providers = useMemo(() => configs.data ?? [], [configs.data]);
  const catalogue = useMemo(() => models.data ?? [], [models.data]);
  const combos = useMemo(() => comboQuery.data ?? [], [comboQuery.data]);

  /**
   * Offer whichever binding this browser last saved, into an empty one.
   *
   * The combo is checked first, and the two memories are separate keys: if the
   * last save used a combo, `prope-last-router-combo` exists, and *that is the
   * mode*. There is no third key saying which — a mode with nothing behind it is
   * not a memory.
   *
   * Three guards, and each is the difference between a default and an override.
   * The resting-state check leaves an existing revision's binding alone —
   * editing shows what that revision binds to, not what was used last — and it
   * deliberately reads `bindingMode`, so a revision opened in combo mode with
   * nothing selected (ADR-0069's drift case) is NOT quietly filled in with
   * somebody's last combo; that choice has to be made again on purpose.
   * `prefilled` makes it a once-per-mount offer. And the membership checks keep
   * a deleted configuration or a deleted combo out of the form: an id the server
   * no longer lists would only become a 422 at save.
   *
   * `shouldDirty: false` throughout. Nobody typed this, and marking the form
   * dirty would make an untouched composer start saving recovery drafts and
   * would defeat the edit screen's unchanged-form shortcut.
   */
  useEffect(() => {
    if (configs.isPending || configs.isError || comboQuery.isPending || prefilled.current) return;
    prefilled.current = true;
    if (bindingMode !== 'single' || providerConfigId !== UNSET) return;

    const rememberedCombo = readLastRouterCombo();
    if (rememberedCombo && combos.some((combo) => combo.combo_id === rememberedCombo.routeComboId)) {
      form.setValue('bindingMode', 'combo', { shouldDirty: false });
      form.setValue('routeComboId', rememberedCombo.routeComboId, { shouldDirty: false });
      return;
    }

    const remembered = readLastProviderBinding();
    if (!remembered) return;
    if (!providers.some((provider) => provider.provider_config_id === remembered.providerConfigId)) return;
    rememberedModel.current = remembered.upstreamModel;
    form.setValue('providerConfigId', remembered.providerConfigId, { shouldDirty: false });
  }, [bindingMode, combos, comboQuery.isPending, configs.isError, configs.isPending, form, providerConfigId, providers]);

  /**
   * The other half of the pair, once the catalogue that can vouch for it has
   * arrived.
   *
   * A model id means nothing except against the configuration that serves it, so
   * this waits for that configuration's catalogue and drops the remembered model
   * if the provider no longer offers it. Dropping leaves a half-binding, which
   * the model select already reports as the error it is — the honest outcome,
   * because the model this person last used is genuinely gone.
   */
  useEffect(() => {
    if (rememberedModel.current === undefined) return;
    // The provider check is not redundant with `isPending`: a disabled query is
    // also a settled one, and consuming the remembered model in the commit that
    // has only just chosen the provider would drop it before the catalogue that
    // vouches for it was ever requested.
    if (providerConfigId === UNSET || models.isPending) return;
    const remembered = rememberedModel.current;
    rememberedModel.current = undefined;
    if (models.isError || !catalogue.some((model) => model.model_id === remembered)) return;
    form.setValue('upstreamModel', remembered, { shouldDirty: false });
  }, [catalogue, form, models.isError, models.isPending, providerConfigId]);

  useEffect(() => {
    if (!focusedFromEvaluation || configs.isPending) return;
    setHighlighted(true);
    sectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    // `#provider-config-select` is not rendered in combo mode, so focusing it
    // silently did nothing for exactly the prompts the evaluation page sends
    // here. The mode switch is first, it always exists, and it is the control
    // somebody arriving to fix a binding may need to change before anything
    // else — so it is the fallback rather than a second selector to keep in
    // step with whichever field happens to be on screen.
    const target = sectionRef.current?.querySelector<HTMLElement>('#provider-config-select')
      ?? sectionRef.current?.querySelector<HTMLElement>('#binding-mode-switch input:checked');
    target?.focus();
    const timeoutId = window.setTimeout(() => setHighlighted(false), PROVIDER_HIGHLIGHT_DURATION_MS);
    return () => window.clearTimeout(timeoutId);
  }, [configs.isPending, focusedFromEvaluation]);

  return (
    <div
      ref={sectionRef}
      className={cn(
        'grid gap-4 rounded-control transition-shadow duration-(--prope-motion-duration-slow) motion-reduce:transition-none',
        highlighted && 'ring-2 ring-secondary ring-offset-4 ring-offset-surface',
      )}
    >
      {/* Values are NOT cleared on switch. Flipping across to look at the other
          option and back must not destroy a choice somebody already made; the
          send site is what makes the two exclusive. */}
      <div id="binding-mode-switch">
        <SegmentedControl
          label={t('lifecycle.editor.bindingMode')}
          name="bindingMode"
          options={[
            { value: 'single', label: t('lifecycle.editor.bindingModeSingle') },
            { value: 'combo', label: t('lifecycle.editor.bindingModeCombo') },
          ]}
          value={bindingMode}
          onValueChange={(value) => form.setValue('bindingMode', value === 'combo' ? 'combo' : 'single', { shouldDirty: true, shouldValidate: true })}
        />
      </div>

      {bindingMode === 'combo' ? (
        <ComboBindingField combos={combos} comboQuery={comboQuery} />
      ) : (
        <SingleBindingFields providers={providers} catalogue={catalogue} configs={configs} models={models} />
      )}
    </div>
  );
}
