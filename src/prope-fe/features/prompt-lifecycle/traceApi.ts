import { apiRequest } from '@/lib/apiClient';
import {
  callObservabilitySchema,
  traceDetailSchema,
  type CallObservability,
  type TraceDetail,
} from '@/features/prompt-lifecycle/traceTypes';

export async function getCallObservability(
  promptId: string,
  callId: string,
  includeRequest: boolean,
): Promise<CallObservability> {
  const search = includeRequest ? '?include_request=true' : '';
  return apiRequest(
    `/api/v1/prompts/${encodeURIComponent(promptId)}/call-records/${encodeURIComponent(callId)}/observability${search}`,
    { schema: callObservabilitySchema },
  );
}

export async function getEvalCaseTrace(runId: string, caseResultId: string): Promise<TraceDetail> {
  return apiRequest(
    `/api/v1/eval-runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(caseResultId)}/trace`,
    { schema: traceDetailSchema },
  );
}
