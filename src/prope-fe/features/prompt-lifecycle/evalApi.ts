import { z } from 'zod';
import { apiRequest } from '@/lib/apiClient';
import {
  attachmentSchema,
  caseResultSchema,
  datasetDeletedSchema,
  datasetDetailSchema,
  datasetSchema,
  evalRunAcceptedSchema,
  evalRunSchema,
  evalSuiteSchema,
  type DatasetAttachment,
  type DatasetDeleted,
  type DatasetWriteInput,
  type EvalCaseResult,
  type EvalDataset,
  type EvalDatasetDetail,
  type EvalRunAccepted,
  type EvalRunDetail,
  type EvalSuiteDetail,
} from '@/features/prompt-lifecycle/evalTypes';
import {
  datasetSuggestSchema,
  evalAnalysisSchema,
  type DatasetSuggest,
  type EvalAnalysis,
} from '@/features/prompt-lifecycle/evalAdvisorTypes';

/**
 * The evaluation module, called for real.
 *
 * No mock arm, for `providerApi.ts`'s reason: a faked eval result is a screen
 * that says a prompt passed when nothing ran, which is worse than a screen that
 * says the stack is down. The one concession is `getDatasets`, which answers
 * with an empty library offline — an empty tree is a state the workspace
 * already renders, and it lets the page load far enough to explain itself.
 */

const dataMode =
  import.meta.env.VITE_DATA_MODE ??
  import.meta.env.VITE_AUTH_MODE ??
  'api';
const useRealApi = dataMode === 'api';

export class EvaluationUnavailable extends Error {
  constructor() {
    super('evaluation needs the real API — start the stack or set VITE_DATA_MODE=api');
    this.name = 'EvaluationUnavailable';
  }
}

function requireRealApi(): void {
  if (!useRealApi) throw new EvaluationUnavailable();
}

export function isEvaluationUnavailable(error: unknown): error is EvaluationUnavailable {
  return error instanceof EvaluationUnavailable;
}

export function evaluationIsLive(): boolean {
  return useRealApi;
}

export async function getDatasets(): Promise<EvalDataset[]> {
  if (!useRealApi) return [];
  return apiRequest('/api/v1/datasets', { schema: z.array(datasetSchema) });
}

export async function getDataset(datasetId: string): Promise<EvalDatasetDetail> {
  // `builtin:<slug>@<n>` needs no escaping — `:` and `@` are legal in a path
  // segment — but a workspace id goes through the same call, so encode both.
  return apiRequest(`/api/v1/datasets/${encodeURIComponent(datasetId)}`, {
    schema: datasetDetailSchema,
  });
}

export async function createDataset(input: DatasetWriteInput): Promise<EvalDatasetDetail> {
  requireRealApi();
  return apiRequest('/api/v1/datasets', {
    method: 'POST',
    body: JSON.stringify(input),
    schema: datasetDetailSchema,
  });
}

export async function updateDataset(
  datasetId: string,
  input: DatasetWriteInput,
): Promise<EvalDatasetDetail> {
  requireRealApi();
  return apiRequest(`/api/v1/datasets/${encodeURIComponent(datasetId)}`, {
    method: 'PUT',
    body: JSON.stringify(input),
    schema: datasetDetailSchema,
  });
}

export async function deleteDataset(datasetId: string): Promise<DatasetDeleted> {
  requireRealApi();
  return apiRequest(`/api/v1/datasets/${encodeURIComponent(datasetId)}`, {
    method: 'DELETE',
    schema: datasetDeletedSchema,
  });
}

/**
 * Ask the agent to draft a dataset from this prompt.
 *
 * The result is a library dataset and is deliberately not attached — the tree
 * shows it in the prompt's folder and somebody ticks it, having read it. Slow
 * by nature: it is one model call over a whole prompt body.
 */
export async function draftDataset(
  promptId: string,
  input: { versionId?: string; folder?: string; caseTarget?: number; brief?: string },
): Promise<EvalDatasetDetail> {
  requireRealApi();
  return apiRequest(`/api/v1/prompts/${encodeURIComponent(promptId)}/datasets/draft`, {
    method: 'POST',
    body: JSON.stringify({
      version_id: input.versionId ?? null,
      folder: input.folder ?? null,
      brief: input.brief ?? null,
      ...(input.caseTarget ? { case_target: input.caseTarget } : {}),
    }),
    schema: datasetDetailSchema,
  });
}

/**
 * Ask the advisor which library sets this prompt's body should be measured
 * with. Advice, never a write: the answer is a ranked list of proposals, and
 * attaching one is the person's own tick. One model call over the catalogue's
 * metadata — the server drops any id the model names that the catalogue never
 * showed, so the answer cannot propose a set that does not exist, and an
 * empty list means nothing truly applies.
 */
export async function suggestDatasets(
  promptId: string,
  input: { versionId?: string },
): Promise<DatasetSuggest> {
  requireRealApi();
  return apiRequest(`/api/v1/prompts/${encodeURIComponent(promptId)}/datasets/suggest`, {
    method: 'POST',
    body: JSON.stringify({ version_id: input.versionId ?? null }),
    schema: datasetSuggestSchema,
  });
}

/**
 * Read this revision's finished runs and answer: what should change?
 *
 * The brief and its findings are a deterministic read of the case results —
 * failures grouped by suite and assertion type, each with fixed advice — so
 * the same results always produce the same brief.
 */
export async function analyzeEvalRuns(
  promptId: string,
  input: { versionId: string },
): Promise<EvalAnalysis> {
  requireRealApi();
  return apiRequest(`/api/v1/prompts/${encodeURIComponent(promptId)}/eval-runs/analysis`, {
    method: 'POST',
    body: JSON.stringify({ version_id: input.versionId }),
    schema: evalAnalysisSchema,
  });
}

export async function getDatasetAttachments(promptId: string): Promise<DatasetAttachment[]> {
  if (!useRealApi) return [];
  return apiRequest(`/api/v1/prompts/${encodeURIComponent(promptId)}/dataset-attachments`, {
    schema: z.array(attachmentSchema),
  });
}

/**
 * The whole tick-state at once. A tick and an untick are the same request, so
 * the caller sends what the prompt should end up attached to rather than a
 * diff — which also means a retry after a dropped response is harmless.
 */
export async function replaceDatasetAttachments(
  promptId: string,
  datasetIds: string[],
): Promise<DatasetAttachment[]> {
  requireRealApi();
  return apiRequest(`/api/v1/prompts/${encodeURIComponent(promptId)}/dataset-attachments`, {
    method: 'PUT',
    body: JSON.stringify({ dataset_ids: datasetIds }),
    schema: z.array(attachmentSchema),
  });
}

export async function startRunsFromAttachments(
  promptId: string,
  versionId: string,
): Promise<EvalRunAccepted> {
  requireRealApi();
  return apiRequest(
    `/api/v1/prompts/${encodeURIComponent(promptId)}/eval-runs/from-attachments`,
    {
      method: 'POST',
      body: JSON.stringify({ version_id: versionId }),
      schema: evalRunAcceptedSchema,
    },
  );
}

export async function getEvalRun(runId: string): Promise<EvalRunDetail> {
  return apiRequest(`/api/v1/eval-runs/${encodeURIComponent(runId)}`, { schema: evalRunSchema });
}

export async function cancelEvalRun(runId: string): Promise<EvalRunDetail> {
  requireRealApi();
  return apiRequest(`/api/v1/eval-runs/${encodeURIComponent(runId)}/cancel`, {
    method: 'POST',
    schema: evalRunSchema,
  });
}

export async function getEvalRunCases(runId: string): Promise<EvalCaseResult[]> {
  return apiRequest(`/api/v1/eval-runs/${encodeURIComponent(runId)}/cases`, {
    schema: z.array(caseResultSchema),
  });
}

/** The suite a run measured with, so a case result can be shown beside its input. */
export async function getEvalSuite(suiteId: string): Promise<EvalSuiteDetail> {
  return apiRequest(`/api/v1/eval-suites/${encodeURIComponent(suiteId)}`, {
    schema: evalSuiteSchema,
  });
}
