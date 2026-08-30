import { MagnifyingGlass } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';

interface DatasetControlRailProps {
  search: string; tag: string; linked: string; sort: string; tags: string[]; count: number;
  onSearch: (value: string) => void; onTag: (value: string) => void; onLinked: (value: string) => void; onSort: (value: string) => void; onClear: () => void;
}

export function DatasetControlRail(props: DatasetControlRailProps) {
  const { t } = useTranslation();
  return <section className="grid gap-3 rounded-xl border border-border bg-subtle p-4" aria-label={t('lifecycle.dataset.controls.label')}>
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[minmax(0,2fr)_repeat(3,minmax(0,1fr))]">
      <Input label={t('lifecycle.dataset.controls.search')} value={props.search} onChange={(event) => props.onSearch(event.currentTarget.value)} leadingIcon={<MagnifyingGlass className="size-4" />} />
      <Select label={t('lifecycle.dataset.controls.tag')} value={props.tag} onValueChange={props.onTag} options={[{ value: 'all', label: t('lifecycle.dataset.controls.allTags') }, ...props.tags.map((value) => ({ value, label: value }))]} />
      <Select label={t('lifecycle.dataset.controls.linked')} value={props.linked} onValueChange={props.onLinked} options={['all', 'linked', 'unlinked'].map((value) => ({ value, label: t(`lifecycle.dataset.controls.linkedOptions.${value}`) }))} />
      <Select label={t('lifecycle.dataset.controls.sort')} value={props.sort} onValueChange={props.onSort} options={['updated', 'name', 'cases'].map((value) => ({ value, label: t(`lifecycle.dataset.controls.sortOptions.${value}`) }))} />
    </div>
    <div className="flex items-center justify-between gap-3"><p className="text-caption text-muted">{t('lifecycle.dataset.controls.results', { count: props.count })}</p><Button type="button" intent="ghost" onClick={props.onClear}>{t('lifecycle.dataset.controls.clear')}</Button></div>
  </section>;
}
