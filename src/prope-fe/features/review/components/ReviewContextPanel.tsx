import { BracketsCurly, ShieldCheck } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import type { ReviewWorkspace } from '@/features/review/types';

interface ReviewContextPanelProps { workspace: ReviewWorkspace; }

export function ReviewContextPanel({ workspace }: ReviewContextPanelProps) {
  const { t } = useTranslation();
  return <section className="grid gap-4 lg:grid-cols-2"><article className="rounded-panel border border-border bg-surface p-5 shadow-panel sm:p-6"><BracketsCurly aria-hidden className="size-6 text-secondary" /><p className="mt-4 text-overline font-semibold text-muted">{t('review.context.usageEyebrow')}</p><h2 className="mt-2 text-heading-3 font-semibold">{workspace.modelName}</h2><p className="mt-2 text-body text-muted">{workspace.usageContext}</p></article><article className="rounded-panel border border-border bg-surface p-5 shadow-panel sm:p-6"><ShieldCheck aria-hidden className="size-6 text-secondary" /><p className="mt-4 text-overline font-semibold text-muted">{t('review.context.fallbackEyebrow')}</p><h2 className="mt-2 text-heading-3 font-semibold">{workspace.fallbackAnswer ? t('review.context.fallbackSet') : t('review.context.fallbackMissing')}</h2><p className="mt-2 text-body text-muted">{workspace.fallbackAnswer || t('review.context.fallbackPassThrough')}</p></article></section>;
}
