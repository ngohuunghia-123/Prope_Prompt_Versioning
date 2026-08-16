import { useQueries } from '@tanstack/react-query';
import {
  evalRunCasesOptions,
  evalRunDetailOptions,
  evalSuiteOptions,
} from '@/features/prompt-lifecycle/queries';
import {
  isTerminal,
  type EvalRunHandle,
  type EvalSuiteReport,
} from '@/features/prompt-lifecycle/evalTypes';

/**
 * Poll the runs a press of "Chạy thử" started, and assemble what to show.
 *
 * **Three queries per run, and only two of them poll.** The run row carries the
 * status and the counts, the case list fills in as the executor writes each
 * result, and the suite is fetched once for its case *names* — a case result
 * carries a `case_id` and no name, so without the suite the list would be a
 * column of ULIDs.
 *
 * The suite never polls: a suite version is immutable by construction (A-004),
 * so once read it cannot be out of date. The other two stop the moment their
 * run reaches a terminal status, which is why this returns `live` — the page
 * uses it to decide whether the run button is still busy.
 */
export function useEvalRunReports(handles: EvalRunHandle[]): {
  reports: EvalSuiteReport[];
  live: boolean;
} {
  const runQueries = useQueries({
    queries: handles.map((handle) => evalRunDetailOptions(handle.run_id)),
  });

  const stillRunning = handles.map((_, index) => {
    const status = runQueries[index]?.data?.status;
    return status === undefined || !isTerminal(status);
  });

  const caseQueries = useQueries({
    queries: handles.map((handle, index) =>
      evalRunCasesOptions(handle.run_id, stillRunning[index] ?? true),
    ),
  });

  const suiteQueries = useQueries({
    queries: handles.map((handle) => evalSuiteOptions(handle.suite_id)),
  });

  // Deliberately not memoised. The only honest dependency is the data inside
  // three arrays of query results, and every cheap key for that (a join, a
  // length) goes stale on exactly the update that matters — a status moving
  // from `running` to `completed` while the counts happen to match. Rebuilding
  // at most eight small objects per render is the cheaper mistake.
  const reports: EvalSuiteReport[] = handles.map((handle, index) => ({
    handle,
    run: runQueries[index]?.data ?? null,
    cases: caseQueries[index]?.data ?? [],
    suite: suiteQueries[index]?.data ?? null,
  }));

  return { reports, live: handles.length > 0 && stillRunning.some(Boolean) };
}
