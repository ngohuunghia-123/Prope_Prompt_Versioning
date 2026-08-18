import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Modal } from '@/components/ui/Modal';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { isApiError } from '@/lib/apiClient';
import { isProvidersUnavailable } from '@/features/prompt-lifecycle/providerApi';
import { PROVIDER_PRESETS, type ProviderPreset, type ProviderRead } from '@/features/prompt-lifecycle/providerTypes';
import { useCreateProviderMutation } from '@/features/prompt-lifecycle/queries';

/**
 * The refusals `POST /api/v1/providers` can answer with that the person can act
 * on. Anything else falls through to a generic message rather than showing a
 * server string, because ADR-0053 keeps display text in the catalogue and the
 * envelope's `message` is for the log.
 */
const KNOWN_CODES = new Set([
  'provider_base_url_refused',
  'provider_key_unavailable',
  'permission_denied',
]);

function errorKey(error: unknown): string {
  if (isProvidersUnavailable(error)) return 'lifecycle.providers.error.mockMode';
  if (isApiError(error) && KNOWN_CODES.has(error.code)) return `lifecycle.providers.error.${error.code}`;
  // The probe runs before anything is stored, so a bad key is the common case
  // here and it comes back as a plain verification failure rather than a code.
  if (isApiError(error) && error.status === 422) return 'lifecycle.providers.error.rejected';
  return 'lifecycle.providers.error.unknown';
}

interface ProviderRegisterDialogProps {
  open: boolean;
  onClose: () => void;
  onRegistered?: (provider: ProviderRead) => void;
}

/**
 * Register one provider configuration.
 *
 * The vendor picker is not a type — `provider_access` has a single adapter, and
 * every option here is the same `openai_compatible` code path. What the picker
 * chooses is a base URL and a starting name, which is the part nobody should
 * have to remember. `OpenAI-compatible` is the option that asks for the URL,
 * because it is the only one that cannot be known ahead of time.
 *
 * The credential is sent once and never comes back. There is no field for it on
 * any read in this module, so the dialog does not offer to show it again.
 */
export function ProviderRegisterDialog({ open, onClose, onRegistered }: ProviderRegisterDialogProps) {
  const { t } = useTranslation();
  const mutation = useCreateProviderMutation();
  const [presetId, setPresetId] = useState<ProviderPreset['id']>('openai');
  const [displayName, setDisplayName] = useState('OpenAI');
  const [baseUrl, setBaseUrl] = useState(PROVIDER_PRESETS[0]?.baseUrl ?? '');
  const [credential, setCredential] = useState('');
  const [nameTouched, setNameTouched] = useState(false);

  // Reset on every open rather than on close: a dialog that reopens holding the
  // last attempt's key is a dialog that submits it by accident.
  useEffect(() => {
    if (!open) return;
    const first = PROVIDER_PRESETS[0];
    setPresetId('openai');
    setDisplayName(first?.label ?? '');
    setBaseUrl(first?.baseUrl ?? '');
    setCredential('');
    setNameTouched(false);
    mutation.reset();
    // `mutation` is not a dependency on purpose — it changes identity on every
    // state transition of the request, which would re-clear the form mid-submit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const choosePreset = (id: string) => {
    const preset = PROVIDER_PRESETS.find((candidate) => candidate.id === id);
    if (!preset) return;
    setPresetId(preset.id);
    setBaseUrl(preset.baseUrl);
    if (!nameTouched) setDisplayName(preset.id === 'custom' ? '' : preset.label);
  };

  // Mirrors the server: `^https://\S+$`, a name, and a credential of at least
  // eight characters. Checked here so the button is honest, not to replace the
  // 422 — the base URL is also resolved and refused if it points inward.
  const complete = displayName.trim().length > 0
    && /^https:\/\/\S+$/.test(baseUrl.trim())
    && credential.trim().length >= 8;

  return (
    <Modal
      open={open}
      title={t('lifecycle.providers.registerTitle')}
      description={t('lifecycle.providers.registerDescription')}
      confirmLabel={t('lifecycle.providers.registerAction')}
      confirmDisabled={!complete}
      confirmLoading={mutation.isPending}
      className="max-h-[90vh] max-w-md overflow-y-auto"
      onClose={onClose}
      onConfirm={() => {
        if (!complete) return;
        mutation.mutate(
          { displayName: displayName.trim(), baseUrl: baseUrl.trim(), credential: credential.trim() },
          { onSuccess: (provider) => { onRegistered?.(provider); onClose(); } },
        );
      }}
    >
      <div className="grid gap-4">
        <Select
          label={t('lifecycle.providers.vendor')}
          options={PROVIDER_PRESETS.map((preset) => ({
            value: preset.id,
            label: preset.id === 'custom' ? t('lifecycle.providers.vendorCustom') : preset.label,
          }))}
          value={presetId}
          onValueChange={choosePreset}
        />
        <Input
          label={t('lifecycle.providers.displayName')}
          value={displayName}
          onChange={(event) => { setDisplayName(event.target.value); setNameTouched(true); }}
        />
        <Input
          label={t('lifecycle.providers.baseUrl')}
          hint={t('lifecycle.providers.baseUrlHint')}
          value={baseUrl}
          spellCheck={false}
          onChange={(event) => setBaseUrl(event.target.value)}
        />
        <Input
          label={t('lifecycle.providers.credential')}
          hint={t('lifecycle.providers.credentialHint')}
          type="password"
          autoComplete="off"
          value={credential}
          onChange={(event) => setCredential(event.target.value)}
        />
        {/* Registration probes the endpoint before it stores anything, so this
            is the one place the wait is worth naming. */}
        {mutation.isPending ? (
          <p role="status" className="text-caption text-muted">{t('lifecycle.providers.verifying')}</p>
        ) : null}
        {mutation.isError ? (
          <p role="alert" className="text-caption text-danger-text">{t(errorKey(mutation.error))}</p>
        ) : null}
      </div>
    </Modal>
  );
}
