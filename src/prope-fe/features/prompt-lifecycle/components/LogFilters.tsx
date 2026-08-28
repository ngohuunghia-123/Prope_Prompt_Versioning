import { useTranslation } from 'react-i18next';

import { Checkbox } from '@/components/ui/Checkbox';
import { Select } from '@/components/ui/Select';
import type { CallOutcome, CallSource } from '@/features/prompt-lifecycle/insightsTypes';

interface LogFiltersProps {
  source: CallSource | 'all';
  outcome: CallOutcome | 'all';
  scopeToRevision: boolean;
  revisionLabel: string | null;
  onSourceChange: (value: CallSource | 'all') => void;
  onOutcomeChange: (value: CallOutcome | 'all') => void;
  onScopeChange: (value: boolean) => void;
}

/**
 * **No free-text search box.** The mock had one, and it searched a description
 * the ledger does not hold — a call record is metadata, and ADR-0018 keeps the
 * request and response text unreadable. Searching ids is what a reader would be
 * left with, which nobody does. The three controls here each map to a real
 * column and are each applied server-side.
 */
/**
 * `eval` is offered by name. Evaluation dispatches through the same provider
 * seam as everything else and writes `ledger.call_record` rows like everything
 * else, so the tokens and the money were always here — but with only `gateway`
 * and `playground` on the select, the one way to see them was `all`, and a run
 * that had just been paid for looked like it had never happened.
 */
const SOURCES: ReadonlyArray<CallSource | 'all'> = ['gateway', 'playground', 'eval', 'all'];
const OUTCOMES: ReadonlyArray<CallOutcome | 'all'> = [
  'all',
  'ok',
  'fallback',
  'truncated',
  'caller_error',
  'upstream_error',
];

export function LogFilters({
  source,
  outcome,
  scopeToRevision,
  revisionLabel,
  onSourceChange,
  onOutcomeChange,
  onScopeChange,
}: LogFiltersProps) {
  const { t } = useTranslation();
  return (
    <div className="grid items-end gap-3 border-b border-border bg-subtle/40 p-4 md:grid-cols-3">
      <Select
        label={t('lifecycle.insights.logs.source')}
        value={source}
        onValueChange={(value) => onSourceChange(value as CallSource | 'all')}
        options={SOURCES.map((value) => ({ value, label: t(`lifecycle.insights.sources.${value}`) }))}
      />
      <Select
        label={t('lifecycle.insights.logs.outcome')}
        value={outcome}
        onValueChange={(value) => onOutcomeChange(value as CallOutcome | 'all')}
        options={OUTCOMES.map((value) => ({ value, label: t(`lifecycle.insights.outcomes.${value}`) }))}
      />
      {revisionLabel ? (
        <Checkbox
          label={t('lifecycle.insights.logs.scopeToRevision', { revision: revisionLabel })}
          checked={scopeToRevision}
          onChange={(event) => onScopeChange(event.target.checked)}
        />
      ) : null}
    </div>
  );
}
