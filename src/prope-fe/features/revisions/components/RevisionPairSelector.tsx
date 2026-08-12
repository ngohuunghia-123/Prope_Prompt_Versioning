import { ArrowRight } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import type { PromptRevision } from '@/features/revisions/types';

interface RevisionPairSelectorProps { promptId: string; revisions: PromptRevision[]; }

export function RevisionPairSelector({ promptId, revisions }: RevisionPairSelectorProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [fromId, setFromId] = useState(revisions.at(-1)?.id ?? '');
  const [toId, setToId] = useState(revisions[0]?.id ?? '');
  const options = revisions.map((revision) => ({ value: revision.id, label: t('revisions.versionWithId', { number: revision.number, id: revision.id }) }));
  return <section className="grid gap-4 rounded-modal border border-border bg-canvas p-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end"><Select label={t('revisions.compare.from')} value={fromId} onValueChange={setFromId} options={options} /><Select label={t('revisions.compare.to')} value={toId} onValueChange={setToId} options={options} /><Button type="button" intent="neutral" disabled={!fromId || !toId || fromId === toId} trailingIcon={<ArrowRight aria-hidden className="size-4" />} onClick={() => navigate(`/app/prompts/${promptId}/revisions/compare/${fromId}?to=${encodeURIComponent(toId)}`)}>{t('revisions.actions.compare')}</Button></section>;
}
