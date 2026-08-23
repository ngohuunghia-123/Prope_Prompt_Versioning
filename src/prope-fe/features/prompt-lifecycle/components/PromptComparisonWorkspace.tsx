import { ArrowsLeftRight, ArrowLeft } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { Select } from '@/components/ui/Select';
import { PromptBlockAccordion } from '@/features/prompt-lifecycle/components/PromptBlockAccordion';
import type { PromptDetail, Revision } from '@/features/prompt-lifecycle/types';

interface PromptComparisonWorkspaceProps {
  prompt: PromptDetail;
  selected: Revision;
  onBack: () => void;
  onUseCandidate: (revisionId: string) => void;
}

export function PromptComparisonWorkspace({ prompt, selected, onBack, onUseCandidate }: PromptComparisonWorkspaceProps) {
  const { t } = useTranslation();
  const selectedIndex = prompt.revisions.findIndex((revision) => revision.id === selected.id);
  const releasedRevision = prompt.revisions.find((revision) => revision.status === 'inUse' && revision.id !== selected.id);
  const fallbackA = releasedRevision ?? prompt.revisions[selectedIndex + 1] ?? prompt.revisions[1] ?? selected;
  const [revisionAId, setRevisionAId] = useState(fallbackA.id);
  const [revisionBId, setRevisionBId] = useState(selected.id);
  const [onlyChanged, setOnlyChanged] = useState(true);
  const revisionA = prompt.revisions.find((revision) => revision.id === revisionAId) ?? fallbackA;
  const revisionB = prompt.revisions.find((revision) => revision.id === revisionBId) ?? selected;
  const options = prompt.revisions.map((revision) => ({ value: revision.id, label: revision.number }));
  return (
    <section aria-labelledby="prompt-compare-title" className="min-w-0 p-4 sm:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
        <div>
          <Button intent="ghost" size="small" leadingIcon={<ArrowLeft aria-hidden className="size-4" />} onClick={onBack}>{t('lifecycle.promptCompare.back')}</Button>
          <h2 id="prompt-compare-title" className="mt-2 font-display text-heading-2 text-ink">{t('lifecycle.promptCompare.title')}</h2>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <Select label={t('lifecycle.promptCompare.baseline')} options={options} value={revisionA.id} onValueChange={setRevisionAId} />
          <Button intent="ghost" size="icon" aria-label={t('lifecycle.promptCompare.swap')} onClick={() => { setRevisionAId(revisionB.id); setRevisionBId(revisionA.id); }}><ArrowsLeftRight aria-hidden className="size-5" /></Button>
          <Select label={t('lifecycle.promptCompare.candidate')} options={options} value={revisionB.id} onValueChange={setRevisionBId} />
        </div>
      </header>
      <div className="my-4 flex flex-wrap items-center justify-between gap-3">
        <Checkbox label={t('lifecycle.promptCompare.onlyChanged')} checked={onlyChanged} onChange={(event) => setOnlyChanged(event.currentTarget.checked)} />
        <Button onClick={() => onUseCandidate(revisionB.id)}>{t('lifecycle.promptCompare.viewCandidate')}</Button>
      </div>
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          [t('lifecycle.promptDetail.author'), `${revisionA.author} → ${revisionB.author}`],
          [t('lifecycle.promptDetail.evalResult'), `${revisionA.evalPassed}/${revisionA.evalTotal} → ${revisionB.evalPassed}/${revisionB.evalTotal}`],
          [t('lifecycle.overview.versioning.costPerCall'), `${revisionA.cost} → ${revisionB.cost}`],
          [t('lifecycle.overview.versioning.changeSummary'), revisionB.summary],
        ].map(([label, value]) => <div key={label} className="rounded-xl border border-border bg-surface p-3"><p className="text-caption text-muted">{label}</p><p className="mt-1 text-body font-semibold text-ink">{value}</p></div>)}
      </div>
      <PromptBlockAccordion beforeBody={revisionA.promptBody} body={revisionB.promptBody} onlyChanged={onlyChanged} sideBySide />
    </section>
  );
}
