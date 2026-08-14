import { Copy, Eye, EyeSlash, Key, Plus, Trash } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { Notification } from '@/components/Notification';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Select } from '@/components/ui/Select';
import { sdkKeysOptions, useGenerateSDKKeyMutation, useRevokeSDKKeyMutation } from '@/features/prompt-lifecycle/queries';
import type { PromoteEnvironment } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { cn } from '@/lib/cn';

interface SdkKeysCardProps { promptId: string; }

export function SdkKeysCard({ promptId }: SdkKeysCardProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const [environment, setEnvironment] = useState<PromoteEnvironment>('production');
  const [visibleKey, setVisibleKey] = useState<string>();
  const [revokeKey, setRevokeKey] = useState<string>();
  const keysQuery = useQuery(sdkKeysOptions(promptId));
  const generate = useGenerateSDKKeyMutation();
  const revoke = useRevokeSDKKeyMutation();
  const options: { value: PromoteEnvironment; label: string }[] = [
    { value: 'development', label: t('lifecycle.overview.production.envDevelopment') },
    { value: 'staging', label: t('lifecycle.overview.production.envStaging') },
    { value: 'production', label: t('lifecycle.overview.production.envProduction') },
  ];

  return (
    <>
      <Card title={t('lifecycle.overview.production.sdkKeys')} action={<div className="flex flex-wrap items-end gap-3"><Select label={t('lifecycle.overview.production.environment')} options={options} value={environment} onValueChange={(value) => setEnvironment(value as PromoteEnvironment)} /><Button size="small" leadingIcon={<Plus aria-hidden className="size-4" />} loading={generate.isPending} onClick={() => generate.mutate({ promptId, environment })}>{t('lifecycle.overview.production.generateKey')}</Button></div>}>
        {generate.isError || revoke.isError ? <Notification tone="error" title={t('lifecycle.states.error.title')}>{t('lifecycle.overview.production.generateError')}</Notification> : null}
        {keysQuery.isPending ? <p role="status">{t('lifecycle.overview.production.loadingKeys')}</p> : keysQuery.isError ? <p role="alert" className="text-danger-text">{t('lifecycle.overview.production.loadError')}</p> : keysQuery.data.length ? (
          <div className="space-y-3">{keysQuery.data.map((sdkKey) => (
            <div key={sdkKey.id} className="flex flex-wrap items-center justify-between gap-4 rounded-modal border border-border bg-subtle p-4">
              <div className="flex min-w-0 items-center gap-3"><span className="grid size-10 shrink-0 place-items-center rounded-xl bg-surface"><Key aria-hidden className="size-5 text-primary" /></span><div className="min-w-0"><div className="flex items-center gap-1"><code className="truncate text-body text-ink">{visibleKey === sdkKey.id ? sdkKey.key : sdkKey.maskedKey}</code><Button intent="ghost" size="icon" onClick={() => setVisibleKey(visibleKey === sdkKey.id ? undefined : sdkKey.id)} aria-label={t(visibleKey === sdkKey.id ? 'lifecycle.overview.production.hideKey' : 'lifecycle.overview.production.showKey')}>{visibleKey === sdkKey.id ? <EyeSlash aria-hidden className="size-4" /> : <Eye aria-hidden className="size-4" />}</Button><Button intent="ghost" size="icon" onClick={() => void navigator.clipboard.writeText(sdkKey.key)} aria-label={t('lifecycle.overview.production.copyKey')}><Copy aria-hidden className="size-4" /></Button></div><p className="text-caption text-muted"><span className={cn('mr-2 rounded-tag px-2 py-0.5', sdkKey.status === 'revoked' ? 'bg-disabled text-disabled-text' : 'bg-success/10 text-success-text')}>{t(`lifecycle.overview.production.status.${sdkKey.status}`)}</span>{t('lifecycle.overview.production.createdValue', { date: format.date(sdkKey.createdAt) })}</p></div></div>
              <Button intent="danger" size="small" leadingIcon={<Trash aria-hidden className="size-4" />} disabled={sdkKey.status === 'revoked'} onClick={() => setRevokeKey(sdkKey.id)}>{t('lifecycle.overview.production.revoke')}</Button>
            </div>
          ))}</div>
        ) : <p className="rounded-modal border border-dashed border-border p-8 text-center text-muted">{t('lifecycle.overview.production.noKeys')}</p>}
      </Card>
      {revokeKey ? <Modal open title={t('lifecycle.overview.production.revokeConfirmTitle')} description={t('lifecycle.overview.production.revokeConfirmDesc')} confirmLabel={t('lifecycle.overview.production.revoke')} destructive onClose={() => setRevokeKey(undefined)} onConfirm={() => revoke.mutate({ promptId, keyId: revokeKey }, { onSuccess: () => setRevokeKey(undefined) })} /> : null}
    </>
  );
}
