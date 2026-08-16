import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Modal } from '@/components/ui/Modal';
import { Input } from '@/components/ui/Input';
import { isProvidersUnavailable } from '@/features/prompt-lifecycle/providerApi';
import { useRotateCredentialMutation } from '@/features/prompt-lifecycle/queries';

/**
 * Replace a stored key.
 *
 * The new one is probed against the configuration's base URL before it replaces
 * anything, so a typo is refused rather than stored and discovered later by a
 * production call. There is no field showing the old key, here or anywhere: the
 * seam is write-only and `credential_last_four` is the whole of what a read
 * returns.
 */
export function RotateCredentialDialog({ providerId, onClose }: { providerId: string | undefined; onClose: () => void }) {
  const { t } = useTranslation();
  const mutation = useRotateCredentialMutation();
  const [credential, setCredential] = useState('');

  useEffect(() => {
    if (!providerId) return;
    setCredential('');
    mutation.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providerId]);

  return (
    <Modal
      open={providerId !== undefined}
      title={t('lifecycle.providers.rotateTitle')}
      description={t('lifecycle.providers.rotateDescription')}
      confirmLabel={t('lifecycle.providers.rotateAction')}
      confirmDisabled={credential.trim().length < 8}
      confirmLoading={mutation.isPending}
      className="max-w-md"
      onClose={onClose}
      onConfirm={() => {
        if (!providerId || credential.trim().length < 8) return;
        mutation.mutate({ providerId, credential: credential.trim() }, { onSuccess: () => onClose() });
      }}
    >
      <div className="grid gap-3">
        <Input
          label={t('lifecycle.providers.credential')}
          hint={t('lifecycle.providers.credentialHint')}
          type="password"
          autoComplete="off"
          value={credential}
          onChange={(event) => setCredential(event.target.value)}
        />
        {mutation.isPending ? (
          <p role="status" className="text-caption text-muted">{t('lifecycle.providers.verifying')}</p>
        ) : null}
        {mutation.isError ? (
          <p role="alert" className="text-caption text-danger-text">
            {t(isProvidersUnavailable(mutation.error) ? 'lifecycle.providers.error.mockMode' : 'lifecycle.providers.error.rejected')}
          </p>
        ) : null}
      </div>
    </Modal>
  );
}
