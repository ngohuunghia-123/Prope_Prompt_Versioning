import { MagnifyingGlass } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { LabelForm } from '@/features/labeling/LabelForm';
import { LabelingQueue } from '@/features/labeling/LabelingQueue';
import { RecordMetadata } from '@/features/labeling/RecordMetadata';
import { labelingQueueOptions, useSaveCallLabelMutation } from '@/features/labeling/queries';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';

export function LabelingPage() {
  const { t } = useTranslation();
  const [filter, setFilter] = useState('unlabeled');
  const [outcome, setOutcome] = useState('all');
  const [sort, setSort] = useState('newest');
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState('');
  const query = useQuery(labelingQueueOptions);
  const save = useSaveCallLabelMutation();
  const allRecords = useMemo(() => query.data ?? [], [query.data]);
  const outcomes = useMemo(() => [...new Set(allRecords.map((record) => record.outcome))].sort(), [allRecords]);
  const records = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase();
    return allRecords
      .filter((record) => filter === 'all' || (filter === 'unlabeled' ? !record.label : Boolean(record.label)))
      .filter((record) => outcome === 'all' || record.outcome === outcome)
      .filter((record) => !needle || `${record.promptTitle} ${record.consumerLabel ?? ''} ${record.revisionNumber ?? ''}`.toLocaleLowerCase().includes(needle))
      .sort((a, b) => sort === 'oldest' ? Date.parse(a.createdAt) - Date.parse(b.createdAt) : sort === 'prompt' ? a.promptTitle.localeCompare(b.promptTitle) : Date.parse(b.createdAt) - Date.parse(a.createdAt));
  }, [allRecords, filter, outcome, search, sort]);
  const selected = records.find((record) => record.callId === selectedId) ?? records[0];
  const labeled = allRecords.filter((record) => record.label).length;
  const progress = allRecords.length ? Math.round((labeled / allRecords.length) * 100) : 0;
  const clear = () => { setFilter('unlabeled'); setOutcome('all'); setSort('newest'); setSearch(''); };

  if (query.isPending) return <QueryState state="loading" loadingLayout="table" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;
  return <section className="grid gap-5">
    <header><p className="text-overline font-bold text-secondary">{t('labeling.eyebrow')}</p><h1 className="font-display text-heading-1 text-ink">{t('labeling.title')}</h1><p className="mt-1 text-body text-muted">{t('labeling.description')}</p></header>
    <div className="grid gap-2 border-y border-border py-4"><div className="flex flex-wrap items-center justify-between gap-2"><strong className="text-body text-ink">{t('labeling.workbench.progress', { labeled, total: allRecords.length })}</strong><span className="text-caption font-semibold text-secondary">{progress}%</span></div><div className="h-2 overflow-hidden rounded-full bg-subtle" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}><div className="h-full rounded-full bg-secondary transition-[width] duration-(--prope-motion-duration-normal)" style={{ width: `${progress}%` }} /></div></div>
    <div className="grid gap-3 rounded-xl border border-border bg-subtle p-4 md:grid-cols-2 xl:grid-cols-[minmax(0,2fr)_repeat(3,minmax(0,1fr))_auto]">
      <Input label={t('labeling.search')} value={search} onChange={(event) => setSearch(event.currentTarget.value)} leadingIcon={<MagnifyingGlass className="size-4" />} />
      <Select label={t('labeling.filter')} value={filter} onValueChange={setFilter} options={['unlabeled', 'labeled', 'all'].map((value) => ({ value, label: t(`labeling.filters.${value}`) }))} />
      <Select label={t('labeling.workbench.outcome')} value={outcome} onValueChange={setOutcome} options={[{ value: 'all', label: t('labeling.workbench.allOutcomes') }, ...outcomes.map((value) => ({ value, label: t(`labeling.outcome.${value}`) }))]} />
      <Select label={t('labeling.workbench.sort')} value={sort} onValueChange={setSort} options={['newest', 'oldest', 'prompt'].map((value) => ({ value, label: t(`labeling.workbench.sortOptions.${value}`) }))} />
      <Button type="button" intent="ghost" className="justify-self-start self-end whitespace-normal px-2" onClick={clear}>{t('labeling.workbench.clear')}</Button>
    </div>
    <div className="grid items-start overflow-hidden rounded-modal border border-border bg-surface lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
      {records.length ? <><div className="max-h-(--container-content) overflow-y-auto border-b border-border lg:border-r lg:border-b-0"><div className="border-b border-border px-4 py-3 text-caption font-semibold text-muted">{t('labeling.workbench.results', { count: records.length })}</div><LabelingQueue records={records} selectedId={selected?.callId} onSelect={setSelectedId} /></div>
      {selected ? <div className="grid gap-6 p-5 xl:sticky xl:top-6 xl:grid-cols-2"><RecordMetadata record={selected} /><div className="grid content-start gap-3"><LabelForm record={selected} saving={save.isPending} onSave={(label) => {
        const next = allRecords.find((record) => record.callId !== selected.callId && !record.label);
        save.mutate({ promptId: selected.promptId, callId: selected.callId, label }, { onSuccess: () => setSelectedId(next?.callId ?? selected.callId) });
      }} />{save.isError ? <p role="alert" className="rounded-lg bg-danger-subtle p-3 text-body text-danger">{t('labeling.workbench.saveError')}</p> : null}</div></div> : null}</> : <div className="lg:col-span-2"><QueryState state="empty" titleOverride={allRecords.length ? t('labeling.workbench.noResultsTitle') : undefined} descriptionOverride={allRecords.length ? t('labeling.workbench.noResultsBody') : undefined} /></div>}
    </div>
  </section>;
}
