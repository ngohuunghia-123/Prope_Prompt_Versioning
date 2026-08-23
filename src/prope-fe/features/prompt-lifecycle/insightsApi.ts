import { z } from 'zod';

import { apiRequest } from '@/lib/apiClient';
import {
  callRecordSchema,
  conversationGraphSchema,
  conversationSummarySchema,
  evalRunSummarySchema,
  promptUsageSchema,
  type CallOutcome,
  type CallRecord,
  type CallSource,
  type ConversationGraph,
  type ConversationSummary,
  type EvalRunSummary,
  type PromptUsage,
  type UsageWindow,
} from '@/features/prompt-lifecycle/insightsTypes';

/**
 * What one prompt has actually done: its calls, its per-app rollup, its runs.
 *
 * **No mock arm, and that is the point of the file.** These three reads replaced
 * fixtures — nine hardcoded log rows, a Shopee/Lazada/TikTok traffic split, and
 * three canned evaluation overviews chosen by a revision's position in a list.
 * Every one of them was convincing, and each said something about a prompt that
 * was not true. A tab that cannot reach the API must say so; a tab that invents
 * a cost figure is worse than a tab that is down, because somebody will make a
 * release decision on it.
 *
 * `evaluationIsLive` and its refusal live in `evalApi.ts` for the same reason
 * and are not duplicated here: an offline stack fails these calls at the fetch,
 * and `QueryState` renders that honestly.
 */

const PAGE_SIZE = 50;

export interface CallRecordQuery {
  promptId: string;
  /** The keyset cursor: the last `call_id` of the previous page. */
  cursor?: string | null;
  /** Defaults to `gateway` at the call site, not here — see `LogsTab`. */
  source?: CallSource | null;
  outcome?: CallOutcome | null;
  versionId?: string | null;
  window?: UsageWindow | null;
  limit?: number;
}

function withParams(input: Record<string, string | number | null | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(input)) {
    if (value !== null && value !== undefined && value !== '') params.set(key, String(value));
  }
  const query = params.toString();
  return query ? `?${query}` : '';
}

/**
 * One page of call metadata, newest first.
 *
 * Every filter goes to the server. Filtering a received page would report "two
 * calls from this app" for a prompt with two thousand, and the number would
 * change as the reader paged.
 */
export async function getPromptCallRecords(query: CallRecordQuery): Promise<CallRecord[]> {
  const search = withParams({
    cursor: query.cursor,
    source: query.source,
    outcome: query.outcome,
    version_id: query.versionId,
    window: query.window,
    limit: query.limit ?? PAGE_SIZE,
  });
  return apiRequest(
    `/api/v1/prompts/${encodeURIComponent(query.promptId)}/call-records${search}`,
    { schema: z.array(callRecordSchema) },
  );
}

export async function getPromptUsage(
  promptId: string,
  window: UsageWindow,
  source: CallSource | null,
): Promise<PromptUsage> {
  const search = withParams({ window, source });
  return apiRequest(`/api/v1/prompts/${encodeURIComponent(promptId)}/usage${search}`, {
    schema: promptUsageSchema,
  });
}

/**
 * A prompt's run history, newest first.
 *
 * `versionId` narrows to the revision selected in the rail. Omitted, it returns
 * every revision's runs — which is what the pass-rate trend is computed from, so
 * both the table and the trend come from one request.
 */
export async function getPromptEvalRuns(
  promptId: string,
  versionId?: string | null,
): Promise<EvalRunSummary[]> {
  const search = withParams({ version_id: versionId });
  return apiRequest(`/api/v1/prompts/${encodeURIComponent(promptId)}/eval-runs${search}`, {
    schema: z.array(evalRunSummarySchema),
  });
}

export { PAGE_SIZE as CALL_RECORD_PAGE_SIZE };

/**
 * The conversations this prompt took part in, most recently active first.
 *
 * Empty is the ordinary answer, not a failure: a customer whose application has
 * not adopted `prope.conversation_id` has no conversations here, and every
 * customer is in that state until they change one line. The tab says so in
 * words rather than rendering an empty table.
 */
export async function getPromptConversations(
  promptId: string,
  window: UsageWindow | null,
  cursor?: string | null,
): Promise<ConversationSummary[]> {
  const search = withParams({ window, cursor, limit: PAGE_SIZE });
  return apiRequest(
    `/api/v1/prompts/${encodeURIComponent(promptId)}/conversations${search}`,
    { schema: z.array(conversationSummarySchema) },
  );
}

/**
 * One conversation as a graph. Not paged — see the route's docstring for why a
 * cursor over a tree is close to meaningless.
 */
export async function getConversationGraph(
  promptId: string,
  conversationId: string,
): Promise<ConversationGraph> {
  return apiRequest(
    `/api/v1/prompts/${encodeURIComponent(promptId)}/conversations/${encodeURIComponent(conversationId)}`,
    { schema: conversationGraphSchema },
  );
}
