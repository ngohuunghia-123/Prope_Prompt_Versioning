import { ArrowsLeftRight, ArrowLeft } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { Select } from '@/components/ui/Select';
import { PromptBlockAccordion } from '@/features/prompt-lifecycle/components/PromptBlockAccordion';
import type { PromptDetail, Revision } from '@/features/prompt-lifecycle/types';
import { useWorkspaceDisplayNames } from '@/features/prompt-lifecycle/useWorkspaceDisplayNames';

interface PromptComparisonWorkspaceProps {
  prompt: PromptDetail;
  selected: Revision;
  onBack: () => void;
  onUseCandidate: (revisionId: string) => void;
}

export function PromptComparisonWorkspace({ prompt, selected, onBack, onUseCandidate }: PromptComparisonWorkspaceProps) {
  const { t } = useTranslation();
  const { userName } = useWorkspaceDisplayNames();
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
      {/* Title and the revision pair share one row — the selects used to sit
          beside the back+title stack, reading as a third, detached group.
          `justify-between` pins the title left and the controls right; on the
          rare column too narrow for both, flex-wrap drops the selects whole
          rather than clipping either side. */}
      <header className="border-b border-border pb-4">
        <Button intent="ghost" size="small" leadingIcon={<ArrowLeft aria-hidden className="size-4" />} onClick={onBack}>{t('lifecycle.promptCompare.back')}</Button>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <h2 id="prompt-compare-title" className="min-w-0 truncate font-display text-heading-2 text-ink">{t('lifecycle.promptCompare.title')}</h2>
          {/* Both selects get one shared width: left to their own sizing they
              shrink-wrap to their labels, and the longer "Bản ứng viên" caption
              made its trigger 30px wider than "Bản gốc" — a lopsided pair around
              the swap button. A fixed width reads as two matched halves. */}
          <div className="flex shrink-0 items-end gap-2">
            <Select className="w-28" label={t('lifecycle.promptCompare.baseline')} options={options} value={revisionA.id} onValueChange={setRevisionAId} />
            <Button intent="ghost" size="icon" aria-label={t('lifecycle.promptCompare.swap')} onClick={() => { setRevisionAId(revisionB.id); setRevisionBId(revisionA.id); }}><ArrowsLeftRight aria-hidden className="size-5" /></Button>
            <Select className="w-28" label={t('lifecycle.promptCompare.candidate')} options={options} value={revisionB.id} onValueChange={setRevisionBId} />
          </div>
        </div>
      </header>
      <div className="my-4 flex flex-wrap items-center justify-between gap-3">
        <Checkbox label={t('lifecycle.promptCompare.onlyChanged')} checked={onlyChanged} onChange={(event) => setOnlyChanged(event.currentTarget.checked)} />
        <Button onClick={() => onUseCandidate(revisionB.id)}>{t('lifecycle.promptCompare.viewCandidate')}</Button>
      </div>
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          [t('lifecycle.promptDetail.author'), `${userName(revisionA.author)} → ${userName(revisionB.author)}`],
          [t('lifecycle.promptDetail.evalResult'), `${revisionA.evalPassed}/${revisionA.evalTotal} → ${revisionB.evalPassed}/${revisionB.evalTotal}`],
          [t('lifecycle.overview.versioning.costPerCall'), `${revisionA.cost} → ${revisionB.cost}`],
          [t('lifecycle.overview.versioning.changeSummary'), revisionB.summary],
        ].map(([label, value]) => <div key={label} className="rounded-xl border border-border bg-surface p-3"><p className="text-caption text-muted">{label}</p><p className="mt-1 text-body font-semibold text-ink">{value}</p></div>)}
      </div>
      <PromptBlockAccordion beforeBody={revisionA.promptBody} body={revisionB.promptBody} onlyChanged={onlyChanged} sideBySide />
    </section>
  );
}
