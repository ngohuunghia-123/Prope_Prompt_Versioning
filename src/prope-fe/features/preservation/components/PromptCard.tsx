import { ArrowRight, Copy, ClockCounterClockwise } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Card } from '@/components/Card';
import { StatusBadge } from '@/components/StatusBadge';
import { Tag } from '@/components/Tag';
import type { PreservedPrompt } from '@/features/preservation/types';

export interface PromptCardProps { prompt: PreservedPrompt; }

export function PromptCard({ prompt }: PromptCardProps) {
  const { t, i18n } = useTranslation();
  const updatedAt = new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium' }).format(new Date(prompt.updatedAt));
  return (
    <Card className="group min-h-64 justify-between transition-transform duration-(--prope-motion-duration-base) ease-standard hover:-translate-y-1 motion-reduce:transform-none">
      <div className="space-y-4">
        <div className="flex items-start justify-between gap-3">
          <StatusBadge tone={prompt.status === 'approved' ? 'active' : 'pending'}>{t(`preservation.status.${prompt.status}`)}</StatusBadge>
          <span className="inline-flex items-center gap-1 text-caption text-muted"><ClockCounterClockwise aria-hidden className="size-4" />{updatedAt}</span>
        </div>
        <div><h2 className="text-heading-3 font-semibold text-ink">{prompt.title}</h2><p className="mt-2 line-clamp-2 text-body text-muted">{prompt.purpose}</p></div>
        <div className="flex flex-wrap gap-2">{prompt.tags.map((tag) => <Tag key={tag} state="neutral">{tag}</Tag>)}</div>
      </div>
      <div className="flex items-center justify-between gap-4 border-t border-border pt-4">
        <span className="inline-flex items-center gap-1.5 text-caption text-muted"><Copy aria-hidden className="size-4" />{t('preservation.portfolio.reuseCount', { count: prompt.reuseCount })}</span>
        <Link to={`/app/prompts/${prompt.id}`} aria-label={t('preservation.portfolio.openNamed', { name: prompt.title })} className="inline-flex min-h-10 items-center gap-2 rounded-control px-2 text-body font-semibold text-link focus-visible:outline-2 focus-visible:outline-focus">
          {t('preservation.actions.open')}<ArrowRight aria-hidden className="size-4 transition-transform group-hover:translate-x-1 motion-reduce:transform-none" />
        </Link>
      </div>
    </Card>
  );
}
