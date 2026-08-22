import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Select } from '@/components/ui/Select';
import { PromptBlockAccordion } from '@/features/prompt-lifecycle/components/PromptBlockAccordion';
import type { Revision } from '@/features/prompt-lifecycle/types';

interface ContentDiffSectionProps {
  revisions: Revision[];
  selectedId: string;
}

/**
 * The version diff, inline in the Content tab.
 *
 * The baseline defaults to the previous revision — the comparison a reader
 * almost always means — and every block carries its own state tag, so an
 * unchanged block can stay collapsed while changed ones open themselves.
 */
export function ContentDiffSection({ revisions, selectedId }: ContentDiffSectionProps) {
  const { t } = useTranslation();
  const others = revisions.filter((revision) => revision.id !== selectedId);
  const [baselineId, setBaselineId] = useState<string>();
  const baseline = others.find((revision) => revision.id === baselineId) ?? others[0];
  const selected = revisions.find((revision) => revision.id === selectedId);

  if (!selected || others.length === 0 || !baseline) return null;

  return (
    <section aria-labelledby="content-diff-heading" className="rounded-modal border border-border bg-surface shadow-panel">
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-border p-4 sm:p-5">
        <div>
          <h2 id="content-diff-heading" className="font-display text-heading-3 text-ink">{t('lifecycle.surface.contentDiff.title')}</h2>
          <p className="mt-1 text-body text-muted">{t('lifecycle.overview.versioning.diffHint')}</p>
        </div>
        <Select
          label={t('lifecycle.surface.contentDiff.baseline')}
          options={others.map((revision) => ({ value: revision.id, label: t('lifecycle.promptDetail.versionValue', { version: revision.number }) }))}
          value={baseline.id}
          onValueChange={setBaselineId}
        />
      </div>
      <div className="p-4 sm:p-5">
        <PromptBlockAccordion beforeBody={baseline.promptBody} body={selected.promptBody} sideBySide />
      </div>
    </section>
  );
}
