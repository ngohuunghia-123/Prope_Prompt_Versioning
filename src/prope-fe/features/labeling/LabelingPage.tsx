import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { LabelForm } from '@/features/labeling/LabelForm';
import { labelingQueueOptions, useSaveCallLabelMutation } from '@/features/labeling/queries';
import type { LabelingRecord } from '@/features/labeling/types';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';

function RecordMetadata({ record }: { record: LabelingRecord }) {
  const { t, i18n } = useTranslation();
  const values = [
    [t('labeling.metadata.revision'), record.revisionNumber ? `r${record.revisionNumber}` : t('labeling.metadata.unavailable')],
    [t('labeling.metadata.consumer'), record.consumerLabel ?? t('labeling.metadata.unavailable')],
    [t('labeling.metadata.outcome'), t(`labeling.outcome.${record.outcome}`)],
    [t('labeling.metadata.time'), new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(record.createdAt))],
  ];
  return (
    <section className="grid content-start gap-4" aria-labelledby="labeling-call-details">
      <div>
        <h2 id="labeling-call-details" className="text-title font-semibold text-ink">{t('labeling.metadata.title')}</h2>
        <p className="mt-1 text-body text-muted">{t('labeling.metadata.description')}</p>
      </div>
      <dl className="grid gap-3 rounded-xl bg-subtle p-4">
        {values.map(([label, value]) => (
          <div key={label} className="grid gap-1 sm:grid-cols-[minmax(0,0.6fr)_minmax(0,1fr)]">
            <dt className="text-caption font-medium text-muted">{label}</dt>
            <dd className="break-words text-body text-ink">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

export function LabelingPage() {
  const { t } = useTranslation();
  const [filter, setFilter] = useState('unlabeled');
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState('');
  const query = useQuery(labelingQueueOptions);
  const save = useSaveCallLabelMutation();
  const records = useMemo(() => (query.data ?? []).filter((record) => {
    const matchesFilter = filter === 'all' || (filter === 'unlabeled' ? !record.label : Boolean(record.label));
    const haystack = `${record.promptTitle} ${record.consumerLabel ?? ''} ${record.revisionNumber ?? ''}`.toLowerCase();
    return matchesFilter && haystack.includes(search.toLowerCase());
  }), [filter, query.data, search]);
  const selected = records.find((record) => record.callId === selectedId) ?? records[0];

  if (query.isPending) return <QueryState state="loading" loadingLayout="table" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;

  return (
    <section className="grid gap-5">
      <header>
        <p className="text-overline font-bold text-secondary">{t('labeling.eyebrow')}</p>
        <h1 className="font-display text-heading-1 text-ink">{t('labeling.title')}</h1>
        <p className="mt-1 text-body text-muted">{t('labeling.description')}</p>
      </header>
      <div className="grid gap-3 sm:grid-cols-2">
        <Input label={t('labeling.search')} value={search} onChange={(event) => setSearch(event.currentTarget.value)} />
        <Select label={t('labeling.filter')} value={filter} onValueChange={setFilter} options={['unlabeled', 'labeled', 'all'].map((value) => ({ value, label: t(`labeling.filters.${value}`) }))} />
      </div>
      <div className="grid min-h-screen overflow-hidden rounded-modal border border-border bg-surface lg:grid-cols-2">
        <div className="overflow-y-auto border-b border-border lg:border-r lg:border-b-0">
          {records.length ? <ul>{records.map((record) => (
            <li key={record.callId}>
              <button type="button" onClick={() => setSelectedId(record.callId)} className="w-full border-b border-border p-4 text-left hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus">
                <strong className="block truncate text-body text-ink">{record.promptTitle} · {record.revisionNumber ? `r${record.revisionNumber}` : t('labeling.metadata.unavailable')}</strong>
                <span className="mt-1 block truncate text-caption text-muted">{record.consumerLabel ?? t('labeling.metadata.unavailable')} · {t(`labeling.outcome.${record.outcome}`)}</span>
              </button>
            </li>
          ))}</ul> : <QueryState state="empty" />}
        </div>
        {selected ? (
          <div className="grid min-h-0 gap-6 overflow-y-auto p-5 xl:grid-cols-2">
            <RecordMetadata record={selected} />
            <LabelForm record={selected} saving={save.isPending} onSave={(label) => save.mutate({ promptId: selected.promptId, callId: selected.callId, label })} />
          </div>
        ) : <QueryState state="empty" />}
      </div>
    </section>
  );
}
