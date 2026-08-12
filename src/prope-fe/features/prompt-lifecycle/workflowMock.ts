import {
  evaluationWorkflowSchema,
  workflowActionSchema,
  type WorkflowAction,
} from '@/features/prompt-lifecycle/types';
import { createEvaluationWorkflow } from '@/features/prompt-lifecycle/workflowData';

/**
 * ============================================================================
 *  NOT IMPLEMENTED. This file answers from fixtures and reaches no server.
 * ============================================================================
 *
 * The evaluation-workflow stepper models a twenty-step agentic pipeline —
 * `RetrieveKnowledge`, `OptimizePrompt`, `StartCanary`, `ObserveCanary`,
 * `PromoteProduction`, `StoreLesson` — and **the backend has no counterpart to any
 * of it.** This is not a missing endpoint. Prope's release path is:
 *
 *     Draft → In review → Approved → Released
 *
 * with eval runs against a fixed suite (`POST /prompts/{id}/eval-runs`,
 * `GET /eval-runs/{id}`, `GET /eval-runs/{id}/cases`,
 * `GET /prompts/{id}/comparison`) and a recorded human approval before anything
 * reaches production. There is no prompt optimiser, no canary, no automatic
 * promotion and no lesson store, and none of those is planned in the MVP — several
 * would contradict the core value, which is that **no prompt reaches production
 * without a recorded human approval**.
 *
 * Everything else under `features/prompt-lifecycle` now talks to the real API.
 * This is the one screen that does not, and it is isolated in its own file so that
 * is visible from the import rather than buried in a branch.
 *
 * **Resolving it is a product decision, not an engineering one.** Either the
 * stepper is rebuilt on the real lifecycle — which is the shape the API already
 * supports — or the pipeline it describes becomes something Prope intends to
 * build, at which point it needs its own module and its own ADRs. Until one of
 * those happens, nothing here should be mistaken for a contract.
 */

const wait = (milliseconds: number) =>
  new Promise((resolve) => window.setTimeout(resolve, milliseconds));

const MOCK_RUN_KEY = 'prope.mock-evaluation-started';
const MOCK_RUN_MILLISECONDS = 1400;

/** FIXTURE. Reaches no server. See this file's header. */
export async function getEvaluationWorkflow(promptId: string) {
  await wait(180);
  const startedAt = Number(window.sessionStorage.getItem(MOCK_RUN_KEY));
  const running = Number.isFinite(startedAt) && Date.now() - startedAt < MOCK_RUN_MILLISECONDS;
  if (!running) window.sessionStorage.removeItem(MOCK_RUN_KEY);
  return evaluationWorkflowSchema.parse(createEvaluationWorkflow(promptId, running));
}

/** FIXTURE. Reaches no server, records nothing, approves nothing. See this file's header. */
export async function submitWorkflowAction(input: WorkflowAction) {
  await wait(360);
  return workflowActionSchema.parse(input);
}

/** FIXTURE. Starts a timer, not a run. The real start is `api.startEvaluation`. */
export async function startMockEvaluation() {
  await wait(700);
  window.sessionStorage.setItem(MOCK_RUN_KEY, String(Date.now()));
}
