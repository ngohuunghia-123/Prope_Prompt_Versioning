import { useQuery } from '@tanstack/react-query';

import type { CallRecord } from '@/features/prompt-lifecycle/insightsTypes';
import type { TraceMessage } from '@/features/prompt-lifecycle/traceTypes';
import {
  evalRunCasesOptions,
  evalRunDetailOptions,
  evalSuiteOptions,
} from '@/features/prompt-lifecycle/queries';

/**
 * What an eval call sent and what came back — read from evaluation's tables.
 *
 * **An eval call has no stored body, by design.** A-055 keeps one copy of that
 * text in one place: the input on the suite's case, the output on the case
 * result, both under evaluation's permissions and evaluation's retention. The
 * ledger row carries `run_id` and `case_id` — required on every eval row by
 * `ck_call_record_eval_calls_carry_run` — and this hook follows them home.
 *
 * Reading the real thing beats copying it into the body store, and not only on
 * principle: `call_body` is deleted on the workspace's retention window and
 * excluded from the backup, so a duplicated eval body would go blank after
 * thirty days while the copy this reads survives the life of the run.
 *
 * Three requests because that is how the data is shaped — the run names its
 * suite, the suite holds the inputs, the run's cases hold the outputs — and all
 * three are already cached by the eval surfaces, so opening a log row for a run
 * the person just watched usually costs nothing.
 */
export function useEvalCallContent(record: CallRecord | undefined, enabled: boolean) {
  const isEval = record?.source === 'eval';
  const runId = isEval ? (record?.run_id ?? '') : '';
  const caseId = isEval ? (record?.case_id ?? '') : '';
  const active = enabled && runId !== '' && caseId !== '';

  const run = useQuery({ ...evalRunDetailOptions(runId), enabled: active });
  // `live: false` — a log row is read after the fact, so there is nothing to
  // poll for. The run query polls itself while the run is still moving.
  const cases = useQuery({ ...evalRunCasesOptions(runId, false), enabled: active });
  const suiteId = run.data?.suite_id ?? '';
  const suite = useQuery({ ...evalSuiteOptions(suiteId), enabled: active && suiteId !== '' });

  if (!active) return { applies: false } as const;

  const isPending = run.isPending || cases.isPending || suite.isPending;
  const isError = run.isError || cases.isError || suite.isError;
  const refetch = () => {
    void run.refetch();
    void cases.refetch();
    void suite.refetch();
  };
  if (isPending || isError) {
    return { applies: true, isPending, isError, refetch, messages: [] as TraceMessage[] } as const;
  }

  const result = cases.data?.find((entry) => entry.case_id === caseId);
  const suiteCase = suite.data?.cases?.find((entry) => entry.case_id === caseId);

  const messages: TraceMessage[] = [];
  for (const [index, turn] of (suiteCase?.input_messages ?? []).entries()) {
    const role = String(turn.role ?? 'user');
    messages.push({
      message_id: `request-${index}`,
      role: role === 'system' || role === 'assistant' || role === 'tool' ? role : 'user',
      content: typeof turn.content === 'string' ? turn.content : JSON.stringify(turn.content, null, 2),
      // Evaluation stores what the suite author wrote and what the model
      // returned, untouched. Nothing on this path redacts, so nothing on this
      // path may claim it did.
      redacted: false,
    });
  }
  if (result?.output_content != null) {
    messages.push({
      message_id: 'response',
      role: 'assistant',
      content: result.output_content,
      redacted: false,
    });
  }

  return {
    applies: true,
    isPending: false,
    isError: false,
    refetch,
    messages,
    caseName: suiteCase?.name ?? null,
    runId,
  } as const;
}
