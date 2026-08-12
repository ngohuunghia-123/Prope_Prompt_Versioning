import { ArrowRight, CheckCircle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { StatusBadge } from '@/components/StatusBadge';
import { buttonVariants } from '@/components/ui/buttonVariants';
import type { SimilarCheckResult } from '@/features/similar-check/types';

interface SimilarResultsProps { result: SimilarCheckResult; }

export function SimilarResults({ result }: SimilarResultsProps) {
  const { t } = useTranslation();
  if (result.matches.length === 0) return <section className="rounded-panel border border-success-strong bg-success p-5 shadow-panel sm:p-7"><CheckCircle aria-hidden className="size-9 text-success-text" weight="fill" /><h2 className="mt-4 text-heading-2 font-semibold">{t('similar.results.emptyTitle')}</h2><p className="mt-2 text-body text-success-text">{t('similar.results.emptyBody')}</p><Link className={buttonVariants({ intent: 'success', className: 'mt-5' })} to="/app/prompts/new">{t('similar.actions.continueRegistration')}<ArrowRight aria-hidden className="size-4" /></Link></section>;
  return <section className="rounded-panel border border-border bg-surface p-5 shadow-panel sm:p-7"><p className="text-overline font-semibold text-muted">{t('similar.results.eyebrow')}</p><h2 className="mt-2 text-heading-2 font-semibold">{t('similar.results.title')}</h2><p className="mt-2 text-body text-muted">{t('similar.results.description')}</p><div className="mt-5 grid gap-3">{result.matches.map((match) => <article key={match.id} className="rounded-modal border border-border bg-canvas p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-heading-3 font-semibold text-ink">{match.title}</h3><p className="mt-1 text-body text-muted">{match.purpose}</p><p className="mt-2 text-caption text-muted">{t('similar.results.owner', { owner: match.ownerName })}</p></div><StatusBadge tone={match.score >= 85 ? 'pending' : 'disabled'}>{t('similar.results.score', { score: match.score })}</StatusBadge></div><Link className={buttonVariants({ intent: 'neutral', className: 'mt-4' })} to={`/app/registry/${match.id}`}>{t('similar.actions.openExisting')}<ArrowRight aria-hidden className="size-4" /></Link></article>)}</div><Link className={buttonVariants({ intent: 'primary', className: 'mt-5' })} to="/app/prompts/new">{t('similar.actions.keepNew')}<ArrowRight aria-hidden className="size-4" /></Link></section>;
}
