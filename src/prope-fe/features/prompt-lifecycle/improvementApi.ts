import { z } from 'zod';

import { apiRequest } from '@/lib/apiClient';
import {
  findingSchema,
  inboxSchema,
  proposalAcceptedSchema,
  proposalDetailSchema,
  scheduleSchema,
  type ImprovementFinding,
  type ImprovementInbox,
  type ImprovementSchedule,
  type ProposalAccepted,
  type ProposalDetail,
} from '@/features/prompt-lifecycle/improvementTypes';

/**
 * INT-045..INT-050. The findings inbox, the per-prompt tab, the two dispositions
 * and the re-probe schedule.
 *
 * **No mock arm.** `insightsApi.ts`'s rule, for its reason and one sharper here:
 * a fabricated finding is worse than an outage, because somebody would act on it
 * — and one of the acts available is accepting a change to a prompt that is
 * serving production traffic. A stack that cannot answer fails at the fetch and
 * `QueryState` renders that honestly.
 *
 * **An empty inbox is the SUCCESS condition**, not an empty state to apologise
 * for. A-162's inversion, reused from ADR-0064: the sweep writes nothing when
 * nothing is wrong, so `findings: []` means the last pass found the workspace
 * healthy. The copy in `improvement.vi.ts` says that rather than *"no data"*.
 */

export async function getInbox(): Promise<ImprovementInbox> {
  return apiRequest('/api/v1/improvement/findings', { schema: inboxSchema });
}

/**
 * The per-prompt tab, beside ADR-0055's call-records tab.
 *
 * Returns dismissed and resolved findings as well as open ones — unlike the
 * inbox, which is a queue. This is the prompt's own degradation history and a
 * reader looking at it has asked for it.
 */
export async function getPromptFindings(promptId: string): Promise<ImprovementFinding[]> {
  return apiRequest(`/api/v1/prompts/${encodeURIComponent(promptId)}/findings`, {
    schema: z.array(findingSchema),
  });
}

/**
 * Not for me, with a reason.
 *
 * The reason is required by the server and by the database, and it is not
 * ceremony: the dismissal rate per `detector_id` decides which detectors get
 * retired (OQ-157), and a rate with no reasons cannot tell *the detector is
 * wrong* from *the remedy is wrong*, which are opposite fixes.
 */
export async function dismissFinding(
  findingId: string,
  reason: string,
): Promise<ImprovementFinding> {
  return apiRequest(`/api/v1/improvement/findings/${encodeURIComponent(findingId)}/dismiss`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
    schema: findingSchema,
  });
}

/**
 * The detail screen, opened deliberately — the one pre-decision body read
 * (ADR-0070 §5). An `llm_edit` proposal's accept button does not render until
 * the candidate body and its diff do; `draft_rationale` renders as a collapsed,
 * machine-attributed note beside the diff, never instead of it.
 */
export async function getProposalDetail(proposalId: string): Promise<ProposalDetail> {
  return apiRequest(`/api/v1/improvement/proposals/${encodeURIComponent(proposalId)}`, {
    schema: proposalDetailSchema,
  });
}

/**
 * Accept a proposal. **This writes no revision** (SR-6).
 *
 * It records the disposition, appends a history event, and returns the candidate
 * body for a prefilled editor. Creating the revision is a SECOND, explicit act
 * the person takes through prompt-registry's own route under `revision.create` —
 * ADR-0066's rule, and chat-orchestrator's `pending_action` shape: the act
 * somebody takes must be the act they can see themselves taking.
 *
 * The call site is therefore responsible for navigating to the editor with the
 * returned body. Nothing has changed about the prompt until they save.
 */
export async function acceptProposal(proposalId: string): Promise<ProposalAccepted> {
  return apiRequest(`/api/v1/improvement/proposals/${encodeURIComponent(proposalId)}/accept`, {
    method: 'POST',
    schema: proposalAcceptedSchema,
  });
}

/** No thank you, with a reason. Nothing is handed back that could be applied. */
export async function dismissProposal(
  proposalId: string,
  reason: string,
): Promise<ProposalAccepted> {
  return apiRequest(`/api/v1/improvement/proposals/${encodeURIComponent(proposalId)}/dismiss`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
    schema: proposalAcceptedSchema,
  });
}

/**
 * The current cadence, or the never-configured default.
 *
 * The server answers `enabled: false`, weekly, nothing selected for a workspace
 * with no row rather than 404-ing, so this never distinguishes *absent* from
 * *off* — a distinction no reader of this screen has a use for. `updated_at` is
 * null in exactly that case and only that case.
 */
export async function readSchedule(workspaceId: string): Promise<ImprovementSchedule> {
  return apiRequest(
    `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/improvement-schedule`,
    { schema: scheduleSchema },
  );
}

/**
 * The re-probe schedule. **Enabling this commits the workspace to a recurring
 * provider charge**, which is why the route declares `spend_ceiling.manage` and
 * not `prompt.edit`, and why the screen shows an estimated weekly cost first.
 *
 * Empty `namespaces` and empty `prompt_ids` with `enabled` true means every
 * released prompt. That is a deliberate choice somebody makes, not an accident of
 * two empty arrays, so the caller should render it as one.
 */
export async function writeSchedule(
  workspaceId: string,
  schedule: {
    enabled: boolean;
    cadence_days: number;
    namespaces: string[];
    prompt_ids: string[];
  },
): Promise<ImprovementSchedule> {
  return apiRequest(
    `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/improvement-schedule`,
    { method: 'PUT', body: JSON.stringify(schedule), schema: scheduleSchema },
  );
}
