import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Notification } from '@/components/Notification';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { LabelForm } from '@/features/labeling/LabelForm';
import { labelingQueueOptions, useSaveCallLabelMutation } from '@/features/labeling/queries';

const OPT_IN_KEY = 'prope-labeling-opt-in';
export function LabelingPage() {
  const { t } = useTranslation();
  const [enabled, setEnabled] = useState(() => localStorage.getItem(OPT_IN_KEY) === 'true');
  const [filter, setFilter] = useState('unlabeled');
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState('');
  const query = useQuery({ ...labelingQueueOptions, enabled });
  const save = useSaveCallLabelMutation();
  const records = useMemo(() => (query.data ?? []).filter((record) => (filter === 'all' || (filter === 'unlabeled' ? !record.label : Boolean(record.label))) && `${record.promptTitle} ${record.app} ${record.revision}`.toLowerCase().includes(search.toLowerCase())), [filter, query.data, search]);
  const selected = records.find((record) => record.callId === selectedId) ?? records[0];
  if (!enabled) return <div className="mx-auto grid max-w-2xl gap-5"><h1 className="font-display text-heading-1 text-ink">{t('labeling.title')}</h1><Notification tone="info" title={t('labeling.optIn.title')}>{t('labeling.optIn.description')}</Notification><Button onClick={() => { localStorage.setItem(OPT_IN_KEY, 'true'); setEnabled(true); }}>{t('labeling.optIn.action')}</Button></div>;
  if (query.isPending) return <QueryState state="loading" loadingLayout="table" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;
  return <section className="grid gap-5"><header><p className="text-overline font-bold text-secondary">{t('labeling.eyebrow')}</p><h1 className="font-display text-heading-1 text-ink">{t('labeling.title')}</h1><p className="mt-1 text-body text-muted">{t('labeling.description')}</p></header><div className="grid gap-3 sm:grid-cols-2"><Input label={t('labeling.search')} value={search} onChange={(event) => setSearch(event.currentTarget.value)} /><Select label={t('labeling.filter')} value={filter} onValueChange={setFilter} options={['unlabeled', 'labeled', 'all'].map((value) => ({ value, label: t(`labeling.filters.${value}`) }))} /></div><div className="grid min-h-[36rem] overflow-hidden rounded-modal border border-border bg-surface lg:grid-cols-[minmax(16rem,0.7fr)_minmax(0,1.3fr)]"><div className="overflow-y-auto border-b border-border lg:border-r lg:border-b-0"><ul>{records.map((record) => <li key={record.callId}><button type="button" onClick={() => setSelectedId(record.callId)} className="w-full border-b border-border p-4 text-left hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus"><strong className="block truncate text-body text-ink">{record.promptTitle} · {record.revision}</strong><span className="mt-1 block truncate text-caption text-muted">{record.app} · {record.outcome}</span></button></li>)}</ul></div>{selected ? <div className="grid min-h-0 overflow-y-auto p-5 xl:grid-cols-2 xl:gap-6"><div className="grid content-start gap-4"><div><h2 className="text-body font-semibold text-ink">{t('labeling.request')}</h2><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-xl bg-subtle p-3 text-caption text-ink">{selected.requestBody}</pre></div><div><h2 className="text-body font-semibold text-ink">{t('labeling.response')}</h2><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-xl bg-subtle p-3 text-caption text-ink">{selected.responseBody}</pre></div></div><LabelForm record={selected} saving={save.isPending} onSave={(label) => save.mutate({ callId: selected.callId, label })} /></div> : <QueryState state="empty" />}</div></section>;
}
