import { ClockCounterClockwise } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import type { AccessRecord } from '@/features/access-management/types';

interface AccessActivityProps { record: AccessRecord; }

export function AccessActivity({ record }: AccessActivityProps) {
  const { t, i18n } = useTranslation();
  const formatDate = (value: string) => new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
  return <section className="rounded-panel border border-border bg-surface p-5 shadow-panel sm:p-7">
    <div className="flex items-start gap-3"><ClockCounterClockwise aria-hidden className="mt-0.5 size-5 shrink-0 text-secondary" /><div><p className="text-overline font-semibold text-muted">{t('accessManagement.activity.eyebrow')}</p><h2 className="mt-2 text-heading-2 font-semibold">{t('accessManagement.activity.title')}</h2></div></div>
    <ol className="mt-5 divide-y divide-border">
      {record.activity.map((event) => <li key={event.id} className="py-4 first:pt-0 last:pb-0">
        <p className="text-body font-semibold">{t(`accessManagement.activity.events.${event.kind}`, { actor: event.actorName, subject: event.subjectName, value: event.value ? t(`accessManagement.activity.values.${event.value}`) : '' })}</p>
        <p className="mt-1 text-caption text-muted">{formatDate(event.occurredAt)}</p>
      </li>)}
    </ol>
  </section>;
}
