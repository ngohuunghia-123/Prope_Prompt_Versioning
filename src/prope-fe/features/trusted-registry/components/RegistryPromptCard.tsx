import { ArrowRight, SealCheck } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Card } from '@/components/Card';
import { StatusBadge } from '@/components/StatusBadge';
import { Tag } from '@/components/Tag';
import type { RegistryPrompt } from '@/features/trusted-registry/types';

export interface RegistryPromptCardProps { prompt: RegistryPrompt; }

const tones = { draft: 'disabled', inReview: 'pending', approved: 'active', inUse: 'active', retired: 'disabled' } as const;

export function RegistryPromptCard({ prompt }: RegistryPromptCardProps) {
  const { t, i18n } = useTranslation();
  const updatedAt = new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium' }).format(new Date(prompt.updatedAt));
  return (
    <Card className="group min-h-72 justify-between transition-transform duration-(--prope-motion-duration-fast) ease-standard hover:-translate-y-0.5 motion-reduce:transform-none">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <StatusBadge tone={tones[prompt.status]}>{t(`trustedRegistry.status.${prompt.status}`)}</StatusBadge>
          <Tag state={prompt.revisionTrust === 'trusted' ? 'success' : 'warning'}>
            {prompt.revisionTrust === 'trusted' ? <SealCheck aria-hidden className="size-4" /> : null}
            {t(`trustedRegistry.revision.${prompt.revisionTrust}`)}
          </Tag>
        </div>
        <div><h2 className="text-heading-3 font-semibold text-ink">{prompt.title}</h2><p className="mt-2 line-clamp-2 text-body text-muted">{prompt.purpose}</p></div>
        <div className="flex flex-wrap gap-2">{prompt.tags.map((tag) => <Tag key={tag} state="neutral">{tag}</Tag>)}</div>
        <dl className="grid grid-cols-2 gap-3 rounded-control bg-subtle p-3 text-caption">
          <div><dt className="text-muted">{t('trustedRegistry.card.owner')}</dt><dd className="mt-1 font-semibold text-ink">{prompt.ownerName}</dd></div>
          <div><dt className="text-muted">{t('trustedRegistry.card.modelName')}</dt><dd className="mt-1 truncate font-semibold text-ink">{prompt.modelName}</dd></div>
          <div><dt className="text-muted">{t('trustedRegistry.card.revision')}</dt><dd className="mt-1 font-semibold text-ink">{t('revisions.version', { number: prompt.currentRevision })}</dd></div>
          <div><dt className="text-muted">{t('trustedRegistry.card.updated')}</dt><dd className="mt-1 font-semibold text-ink">{updatedAt}</dd></div>
        </dl>
      </div>
      <div className="flex items-center justify-between gap-3 border-t border-border pt-4">
        <span className="inline-flex items-center gap-1.5 text-caption text-muted">{t(`trustedRegistry.access.${prompt.accessLevel}`)}</span>
        <Link to={`/app/registry/${prompt.id}`} aria-label={t('trustedRegistry.card.openNamed', { name: prompt.title })} className="inline-flex min-h-10 items-center gap-2 rounded-control px-2 text-body font-semibold text-link focus-visible:outline-2 focus-visible:outline-focus">
          {t('trustedRegistry.card.open')}<ArrowRight aria-hidden className="size-4 transition-transform group-hover:translate-x-0.5 motion-reduce:transform-none" />
        </Link>
      </div>
    </Card>
  );
}
