import { CheckCircle, Coins, WarningCircle, XCircle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Notification } from '@/components/Notification';
import type { ReviewWorkspace } from '@/features/review/types';

interface ReviewEvidenceSummaryProps { workspace: ReviewWorkspace; }

export function ReviewEvidenceSummary({ workspace }: ReviewEvidenceSummaryProps) {
  const { t } = useTranslation();
  const totals = workspace.suites.reduce((result, suite) => ({ passed: result.passed + suite.passed, failed: result.failed + suite.failed, errored: result.errored + suite.errored }), { passed: 0, failed: 0, errored: 0 });
  const totalCostDelta = workspace.suites.every((suite) => suite.costDelta !== null) ? workspace.suites.reduce((total, suite) => total + (suite.costDelta ?? 0), 0) : null;
  const metrics = [
    { id: 'passed', icon: CheckCircle, value: totals.passed, label: t('review.evidence.passed'), tone: 'text-success-text' },
    { id: 'failed', icon: XCircle, value: totals.failed, label: t('review.evidence.failed'), tone: 'text-danger-text' },
    { id: 'errored', icon: WarningCircle, value: totals.errored, label: t('review.evidence.errored'), tone: 'text-warning-strong' },
    { id: 'cost', icon: Coins, value: totalCostDelta === null ? t('review.evidence.costWithheld') : t('review.evidence.costValue', { delta: totalCostDelta }), label: t('review.evidence.cost'), tone: 'text-info-strong' },
  ];
  return <section className="rounded-panel border border-border bg-surface p-5 shadow-panel sm:p-7"><p className="text-overline font-semibold text-muted">{t('review.evidence.eyebrow')}</p><h2 className="mt-2 text-heading-2 font-semibold">{t('review.evidence.title')}</h2><div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{metrics.map(({ id, icon: Icon, value, label, tone }) => <article key={id} className="rounded-modal border border-border bg-canvas p-4"><Icon aria-hidden className={`size-5 ${tone}`} weight="fill" /><p className="mt-4 text-heading-2 font-semibold text-ink">{value}</p><p className="text-caption text-muted">{label}</p></article>)}</div><div className="mt-5 overflow-hidden rounded-modal border border-border"><ul className="divide-y divide-border">{workspace.suites.map((suite) => <li key={suite.name} className="grid gap-2 bg-canvas p-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"><div><p className="text-body font-semibold text-ink">{suite.name} · {t('review.evidence.suiteVersion', { version: suite.version })}</p><p className="mt-1 text-caption text-muted">{t('review.evidence.modality', { modality: t(`review.evidence.modalities.${suite.modality}`) })}</p></div><p className="text-caption text-muted">{t('review.evidence.suiteResult', { passed: suite.passed, failed: suite.failed, errored: suite.errored })}</p></li>)}</ul></div>{workspace.requiresAcknowledgement ? <Notification className="mt-5 max-w-none" tone="info" title={t('review.evidence.warningTitle')}>{t('review.evidence.warningBody')}</Notification> : null}</section>;
}
