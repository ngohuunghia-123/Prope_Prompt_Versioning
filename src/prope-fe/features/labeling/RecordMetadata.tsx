import { useTranslation } from 'react-i18next';
import type { LabelingRecord } from '@/features/labeling/types';

export function RecordMetadata({ record }: { record: LabelingRecord }) {
  const { t, i18n } = useTranslation();
  const values = [
    [t('labeling.metadata.revision'), record.revisionNumber ? `r${record.revisionNumber}` : t('labeling.metadata.unavailable')],
    [t('labeling.metadata.consumer'), record.consumerLabel ?? t('labeling.metadata.unavailable')],
    [t('labeling.metadata.outcome'), t(`labeling.outcome.${record.outcome}`)],
    [t('labeling.metadata.time'), new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(record.createdAt))],
  ];
  return <section className="grid content-start gap-4" aria-labelledby="labeling-call-details">
    <div><h2 id="labeling-call-details" className="text-title font-semibold text-ink">{t('labeling.metadata.title')}</h2><p className="mt-1 text-body text-muted">{t('labeling.metadata.description')}</p></div>
    <dl className="grid gap-3 rounded-xl bg-subtle p-4">{values.map(([label, value]) => <div key={label} className="grid gap-1 sm:grid-cols-[minmax(0,0.6fr)_minmax(0,1fr)]"><dt className="text-caption font-medium text-muted">{label}</dt><dd className="break-words text-body text-ink">{value}</dd></div>)}</dl>
  </section>;
}
