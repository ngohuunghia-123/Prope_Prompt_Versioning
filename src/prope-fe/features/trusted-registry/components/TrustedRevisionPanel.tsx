import { CheckCircle, Copy, SealCheck } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Notification } from '@/components/Notification';
import { StatusBadge } from '@/components/StatusBadge';
import { Tag } from '@/components/Tag';
import { Button } from '@/components/ui/Button';
import type { RegistryPrompt } from '@/features/trusted-registry/types';

export interface TrustedRevisionPanelProps { prompt: RegistryPrompt; }

export function TrustedRevisionPanel({ prompt }: TrustedRevisionPanelProps) {
  const { t, i18n } = useTranslation();
  const [copied, setCopied] = useState(false);
  const updatedAt = new Intl.DateTimeFormat(i18n.language, { dateStyle: 'long', timeStyle: 'short' }).format(new Date(prompt.updatedAt));
  const copyPrompt = async () => { await navigator.clipboard?.writeText(prompt.content).catch(() => undefined); setCopied(true); };
  return (
    <>
      <article className="overflow-hidden rounded-panel border border-success-strong bg-surface shadow-floating">
        <header className="border-b border-border p-5 sm:p-8">
          <div className="flex flex-wrap items-center gap-2"><StatusBadge tone="active">{t(`trustedRegistry.status.${prompt.status}`)}</StatusBadge><Tag state="success"><SealCheck aria-hidden className="size-4" />{t('trustedRegistry.detail.trusted')}</Tag>{prompt.tags.map((tag) => <Tag key={tag} state="neutral">{tag}</Tag>)}</div>
          <div className="mt-6 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between"><div className="max-w-copy"><p className="text-overline font-semibold text-success-text">{t('trustedRegistry.detail.revisionLabel', { revision: prompt.trustedRevision })}</p><h1 className="mt-2 text-heading-1 font-semibold sm:text-display-2">{prompt.title}</h1><p className="mt-3 text-body-large text-muted">{prompt.purpose}</p></div><Button leadingIcon={<Copy aria-hidden className="size-4" />} onClick={() => void copyPrompt()}>{t('trustedRegistry.actions.copy')}</Button></div>
        </header>
        <div className="grid gap-6 p-5 sm:p-8 lg:grid-cols-[minmax(0,1fr)_17rem]">
          <section aria-labelledby="trusted-content"><h2 id="trusted-content" className="text-overline font-semibold text-muted">{t('trustedRegistry.detail.content')}</h2><pre className="mt-3 whitespace-pre-wrap rounded-modal border border-border bg-canvas p-5 font-sans text-body leading-6 text-ink shadow-inset">{prompt.content}</pre></section>
          <aside className="space-y-5 rounded-modal bg-subtle p-5"><div><p className="text-caption text-muted">{t('trustedRegistry.card.owner')}</p><p className="mt-1 text-body font-semibold">{prompt.ownerName}</p></div><div><p className="text-caption text-muted">{t('trustedRegistry.card.modelName')}</p><p className="mt-1 break-all text-body font-semibold">{prompt.modelName}</p></div><div><p className="text-caption text-muted">{t('trustedRegistry.detail.currentRevision')}</p><p className="mt-1 text-body font-semibold">{t('revisions.version', { number: prompt.currentRevision })}</p></div><div><p className="text-caption text-muted">{t('trustedRegistry.detail.versionId')}</p><p className="mt-1 break-all text-body font-semibold">{prompt.trustedVersionId}</p></div><div><p className="text-caption text-muted">{t('trustedRegistry.card.updated')}</p><p className="mt-1 text-body font-semibold">{updatedAt}</p></div><p className="inline-flex items-center gap-2 text-caption font-semibold text-success-text"><CheckCircle aria-hidden className="size-4" />{t('trustedRegistry.detail.verified')}</p></aside>
        </div>
      </article>
      {copied ? <Notification title={t('trustedRegistry.detail.copiedTitle')} onDismiss={() => setCopied(false)}>{t('trustedRegistry.detail.copiedBody')}</Notification> : null}
    </>
  );
}
