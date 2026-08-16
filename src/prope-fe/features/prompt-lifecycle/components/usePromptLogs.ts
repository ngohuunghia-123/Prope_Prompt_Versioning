import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { promptCallRecordsOptions } from '@/features/prompt-lifecycle/queries';
import type { CallOutcome, CallRecord, CallSource } from '@/features/prompt-lifecycle/insightsTypes';

/**
 * One page of a prompt's calls, plus the filters that produced it.
 *
 * **Every filter is a request, not a `.filter()`.** The endpoint pages on a
 * keyset, so narrowing what has already arrived would report "three calls from
 * this app" for a prompt with three thousand — and a different number on the
 * next page. That was how the mock behaved, and it is the reason this hook holds
 * filter state rather than the table holding it.
 *
 * **`source` defaults to `gateway`.** The tab is called production, so it opens
 * on production traffic; the person's own playground turns are one control away
 * and, when revealed, raise the totals to what the workspace actually spent.
 *
 * Paging is a cursor stack rather than a page number, because the endpoint has
 * no offset: going back means remembering where each page began.
 */
export function usePromptLogs(promptId: string, revisionId: string | null) {
  const [source, setSource] = useState<CallSource | 'all'>('gateway');
  const [outcome, setOutcome] = useState<CallOutcome | 'all'>('all');
  const [scopeToRevision, setScopeToRevision] = useState(false);
  const [cursors, setCursors] = useState<string[]>([]);
  const [selected, setSelected] = useState<CallRecord>();

  const cursor = cursors.at(-1) ?? null;
  const query = useQuery(
    promptCallRecordsOptions({
      promptId,
      cursor,
      source: source === 'all' ? null : source,
      outcome: outcome === 'all' ? null : outcome,
      versionId: scopeToRevision ? revisionId : null,
    }),
  );

  // A filter change invalidates where we were in the keyset: the cursor names a
  // row that the new filter may not even return.
  const reset = () => {
    setCursors([]);
    setSelected(undefined);
  };
  useEffect(reset, [promptId, revisionId, source, outcome, scopeToRevision]);

  const records = query.data ?? [];
  // The API answers a short page when it has run out. There is no total to
  // count against, and asking for one would mean a second full scan of the
  // largest table in the system.
  const hasMore = records.length > 0 && records.length === 50;

  return {
    query,
    records,
    selected,
    source,
    outcome,
    scopeToRevision,
    page: cursors.length + 1,
    hasMore,
    hasPrevious: cursors.length > 0,
    setSource: (value: CallSource | 'all') => setSource(value),
    setOutcome: (value: CallOutcome | 'all') => setOutcome(value),
    setScopeToRevision,
    nextPage: () => {
      const last = records.at(-1);
      if (last) setCursors((current) => [...current, last.call_id]);
    },
    previousPage: () => setCursors((current) => current.slice(0, -1)),
    selectRecord: setSelected,
    closeDetail: () => setSelected(undefined),
  };
}
