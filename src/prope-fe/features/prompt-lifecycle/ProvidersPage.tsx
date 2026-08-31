import { CaretDown, CaretRight, Key, PlugsConnected, ShieldCheck, Trash } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { StatusBadge } from '@/components/StatusBadge';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { useAgentSurface } from '@/features/chat/AgentSurfaceContext';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { ProviderModelList } from '@/features/prompt-lifecycle/components/ProviderModelList';
import { ProviderRegisterDialog } from '@/features/prompt-lifecycle/components/ProviderRegisterDialog';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { RotateCredentialDialog } from '@/features/prompt-lifecycle/components/RotateCredentialDialog';
import { providerErrorKeys, providerErrorValues } from '@/features/prompt-lifecycle/providerErrors';
import type { ProviderRead } from '@/features/prompt-lifecycle/providerTypes';
import {
  providerConfigsOptions,
  useDeleteProviderMutation,
  useVerifyProviderMutation,
} from '@/features/prompt-lifecycle/queries';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';

const BADGE_TONE = {
  passed: 'active',
  pending: 'pending',
  failed: 'error',
} as const;

/**
 * One provider configuration.
 *
 * The verification state is the headline rather than the status, because
 * `active` only says nobody disabled it — `passed` is the one that says a call
 * would actually reach the vendor. A failed probe shows its reason: that string
 * comes from the server's own classification of the failure, not from a message
 * meant for a person, so it renders as evidence beside the badge and not as the
 * explanation itself.
 */
function ProviderCard({ provider, onRotate, onDelete }: {
  provider: ProviderRead;
  onRotate: () => void;
  onDelete: () => void;
}) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const verify = useVerifyProviderMutation();
  const [expanded, setExpanded] = useState(false);

  return (
    <Card title={provider.display_name}>
      <div className="mt-2 grid gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge tone={BADGE_TONE[provider.verification_status]}>
            {t(`lifecycle.providers.state.${provider.verification_status}`)}
          </StatusBadge>
          {provider.status === 'disabled' ? (
            <StatusBadge tone="disabled">{t('lifecycle.providers.disabled')}</StatusBadge>
          ) : null}
          {provider.last_verified_at ? (
            <span className="text-caption text-muted">
              {t('lifecycle.providers.lastVerified', { date: format.date(provider.last_verified_at) })}
            </span>
          ) : null}
        </div>

        <dl className="grid gap-1 text-caption">
          <div className="flex flex-wrap gap-2">
            <dt className="text-muted">{t('lifecycle.providers.baseUrl')}</dt>
            <dd className="min-w-0 truncate font-mono text-ink">{provider.base_url}</dd>
          </div>
          <div className="flex flex-wrap gap-2">
            <dt className="text-muted">{t('lifecycle.providers.credential')}</dt>
            {/* All a read ever returns of the secret, and the reason the rotate
                dialog offers no way to look at the current one. */}
            <dd className="font-mono text-ink">••••{provider.credential_last_four ?? '····'}</dd>
          </div>
        </dl>

        {provider.verification_status === 'failed' && provider.verification_error ? (
          <p className="rounded-lg border border-danger-strong bg-danger px-3 py-2 text-caption text-danger-text">
            {t('lifecycle.providers.failureReason', { reason: provider.verification_error })}
          </p>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            intent="neutral"
            size="small"
            loading={verify.isPending}
            leadingIcon={<ShieldCheck aria-hidden className="size-4" />}
            onClick={() => verify.mutate(provider.provider_config_id)}
          >
            {t('lifecycle.providers.verify')}
          </Button>
          <Button type="button" intent="neutral" size="small" leadingIcon={<Key aria-hidden className="size-4" />} onClick={onRotate}>
            {t('lifecycle.providers.rotate')}
          </Button>
          <Button type="button" intent="neutral" size="small" leadingIcon={<Trash aria-hidden className="size-4" />} onClick={onDelete}>
            {t('lifecycle.providers.delete')}
          </Button>
          <Button
            type="button"
            intent="neutral"
            size="small"
            aria-expanded={expanded}
            leadingIcon={expanded ? <CaretDown aria-hidden className="size-4" /> : <CaretRight aria-hidden className="size-4" />}
            onClick={() => setExpanded((current) => !current)}
          >
            {t('lifecycle.providers.models.toggle')}
          </Button>
        </div>

        {verify.isError ? (
          <p role="alert" className="text-caption text-danger-text">
            {t(providerErrorKeys(verify.error), providerErrorValues(verify.error))}
          </p>
        ) : null}

        {/* Mounted only once opened: each one costs a catalogue request, and a
            workspace with eight providers should not make eight on arrival. */}
        {expanded ? <ProviderModelList providerId={provider.provider_config_id} /> : null}
      </div>
    </Card>
  );
}

/**
 * Provider management, against the real `provider_access` module.
 *
 * What this replaced was a form that posted to a mock and a card list built from
 * a hardcoded array — so a key typed here went nowhere and a prompt could never
 * name a provider that existed. Everything on screen now comes from
 * `GET /api/v1/providers`, and the credential is write-only end to end.
 */
export function ProvidersPage() {
  const { t } = useTranslation();
  const { highlight } = useAgentSurface();
  const query = useQuery(providerConfigsOptions);
  const remove = useDeleteProviderMutation();
  const [registering, setRegistering] = useState(false);
  const [rotating, setRotating] = useState<string>();
  const [deleting, setDeleting] = useState<ProviderRead>();

  const providers = query.data ?? [];

  return (
    <div className="grid gap-6">
      <PageIntro
        eyebrow={t('lifecycle.providers.eyebrow')}
        title={t('lifecycle.providers.title')}
        description={t('lifecycle.providers.description')}
        action={
          <Button type="button" leadingIcon={<PlugsConnected aria-hidden className="size-4" />} onClick={() => setRegistering(true)}>
            {t('lifecycle.providers.registerAction')}
          </Button>
        }
      />

      {query.isPending ? <QueryState state="loading" loadingLayout="table" /> : null}
      {query.isError ? <QueryState state="error" onRetry={() => void query.refetch()} /> : null}

      {!query.isPending && !query.isError && providers.length === 0 ? (
        <QueryState
          state="empty"
          titleOverride={t('lifecycle.providers.empty.title')}
          descriptionOverride={t('lifecycle.providers.empty.body')}
        />
      ) : null}

      {providers.length > 0 ? (
        <div
          className={`grid gap-4 lg:grid-cols-2${highlight === 'providers-list' ? ' rounded-modal ring-2 ring-secondary ring-offset-2 ring-offset-canvas' : ''}`}
        >
          {providers.map((provider) => (
            <ProviderCard
              key={provider.provider_config_id}
              provider={provider}
              onRotate={() => setRotating(provider.provider_config_id)}
              onDelete={() => setDeleting(provider)}
            />
          ))}
        </div>
      ) : null}

      <ProviderRegisterDialog open={registering} onClose={() => setRegistering(false)} />
      <RotateCredentialDialog providerId={rotating} onClose={() => setRotating(undefined)} />

      {/* Deleting is not a soft state change: the configuration and its stored
          credential go, and any revision that named it keeps the id as a value
          that no longer resolves. Said plainly rather than softened. */}
      <Modal
        open={deleting !== undefined}
        destructive
        title={t('lifecycle.providers.deleteTitle')}
        description={t('lifecycle.providers.deleteDescription', { name: deleting?.display_name ?? '' })}
        confirmLabel={t('lifecycle.providers.delete')}
        confirmLoading={remove.isPending}
        onClose={() => setDeleting(undefined)}
        onConfirm={() => {
          if (!deleting) return;
          remove.mutate(deleting.provider_config_id, { onSuccess: () => setDeleting(undefined) });
        }}
      >
        {remove.isError ? (
          <p role="alert" className="text-caption text-danger-text">
            {t(providerErrorKeys(remove.error), providerErrorValues(remove.error))}
          </p>
        ) : null}
      </Modal>
    </div>
  );
}
