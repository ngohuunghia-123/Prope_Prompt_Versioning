import { z } from 'zod';
import { apiRequest, isApiError } from '@/lib/apiClient';
import {
  toCallRecord,
  toProvider,
  toPrompt,
  toRevision,
  revisionLabel,
} from '@/features/prompt-lifecycle/adapters';
import {
  wireCallRecordSchema,
  wireMemberPageSchema,
  wireModelSchema,
  wireProviderSchema,
  wirePromptSchema,
  wirePromptIndexJobSchema,
  wirePromptIndexPreviewSchema,
  wirePromptIndexStatusSchema,
  wirePromptSearchResponseSchema,
  wireReleaseSchema,
  wireReviewScreenSchema,
  wireReviewTaskSchema,
  wireRevisionSchema,
  wireRevisionSummarySchema,
  type WireReviewScreen,
} from '@/features/prompt-lifecycle/wire';
import {
  promptEditorSchema,
  providerFormSchema,
  releaseFormSchema,
  type PromptEditorValues,
  type ProviderFormValues,
  type ReleaseFormValues,
} from '@/features/prompt-lifecycle/types';

/**
 * INT-024, INT-025, INT-026, INT-027 and ADR-0055, called over HTTP.
 *
 * **This file used to be eighty lines of fixtures.** Everything below now reaches
 * the real API; `wire.ts` holds the response shapes and `adapters.ts` maps them
 * onto what the screens read, so a backend rename lands in one adapter rather
 * than in nine components.
 *
 * **One thing is still mocked and it is marked**: the evaluation workflow stepper
 * (`getEvaluationWorkflow`, `submitWorkflowAction`) models a twenty-step agentic
 * pipeline — optimise, canary, promote, store-lesson — that the backend has no
 * counterpart to. Prope's real lifecycle is Draft → In review → Approved →
 * Released, plus eval runs against a fixed suite. Those functions still answer
 * from `workflowData.ts` and say so at their definitions.
 *
 * **Names are best effort.** The API returns `usr_...` ids, and the only endpoint
 * that resolves them is `GET /workspaces/{id}/members`, which is gated on
 * `workspace.manage_members` — Admins only. `loadMemberNames` swallows the
 * refusal and the adapters fall back to the id.
 */

const EMPTY_NAMES: ReadonlyMap<string, string> = new Map();

/**
 * `usr_...` → display name, for whoever can read the member list.
 *
 * Refusals are swallowed on purpose. A Reviewer has no `workspace.manage_members`
 * and gets a `403`; a non-member gets a `404`. Neither is a failure of the screen
 * that wanted a name — the screen renders ids instead, which is the honest
 * degradation and the one an Admin can still act on.
 */
export async function loadMemberNames(workspaceId: string): Promise<ReadonlyMap<string, string>> {
  try {
    const page = await apiRequest(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}/members`, {
      schema: wireMemberPageSchema,
      notifyUnauthorized: false,
    });
    return new Map(
      page.items
        .filter((member) => member.display_name)
        .map((member) => [member.user_id, member.display_name as string]),
    );
  } catch (error) {
    if (isApiError(error) && (error.status === 403 || error.status === 404)) return EMPTY_NAMES;
    throw error;
  }
}

// ---------------------------------------------------------------------------
// Prompts
// ---------------------------------------------------------------------------

export async function getPrompts(workspaceId: string) {
  const [prompts, names] = await Promise.all([
    apiRequest('/api/v1/prompts', { schema: z.array(wirePromptSchema) }),
    loadMemberNames(workspaceId),
  ]);
  // No per-prompt revision fetch here, deliberately: it would be one request per
  // row on the screen most likely to be open, to sharpen a status label. See
  // `adapters.lifecycleStatus`.
  return prompts.map((prompt) => toPrompt(prompt, names));
}

export function searchPrompts(query: string, type: 'quick' | 'ai') {
  const params = new URLSearchParams({ q: query, type });
  return apiRequest(`/api/v1/prompts/search?${params.toString()}`, {
    schema: wirePromptSearchResponseSchema,
  });
}

export function getPromptIndexStatus(promptId: string) {
  return apiRequest(`/api/v1/prompts/${encodeURIComponent(promptId)}/index`, {
    schema: wirePromptIndexStatusSchema,
  });
}

export function previewPromptIndex(promptId: string) {
  return apiRequest(`/api/v1/prompts/${encodeURIComponent(promptId)}/index/preview`, {
    schema: wirePromptIndexPreviewSchema,
  });
}

export function triggerPromptIndex(promptId: string) {
  return apiRequest(`/api/v1/prompts/${encodeURIComponent(promptId)}/index`, {
    method: 'POST',
    body: JSON.stringify({}),
    schema: z.object({ job_id: z.string() }),
  });
}

export function getPromptIndexJob(jobId: string) {
  return apiRequest(`/api/v1/prompt-search/jobs/${encodeURIComponent(jobId)}`, {
    schema: wirePromptIndexJobSchema,
  });
}

export function deletePromptIndex(promptId: string) {
  return apiRequest(`/api/v1/prompts/${encodeURIComponent(promptId)}/index`, {
    method: 'DELETE',
    schema: z.object({ success: z.boolean() }),
  });
}

/**
 * The detail screen's whole payload: the prompt, its revision chain, and the body
 * of whichever revision is the interesting one.
 *
 * Three requests rather than one because there is no endpoint that composes them
 * — and composing them on the server would mean prompt-registry deciding which
 * revision a screen cares about, which is the screen's question.
 *
 * The body comes from the **released** revision when there is one and the newest
 * otherwise, which is what somebody opening a prompt is asking to see.
 */
export async function getPrompt(promptId: string, workspaceId: string) {
  const id = encodeURIComponent(promptId);
  const [prompt, revisions, names] = await Promise.all([
    apiRequest(`/api/v1/prompts/${id}`, { schema: wirePromptSchema }),
    apiRequest(`/api/v1/prompts/${id}/revisions`, { schema: z.array(wireRevisionSummarySchema) }),
    loadMemberNames(workspaceId),
  ]);

  // `GET /prompts/{id}/revisions` is newest-first (ordered by revision_number DESC).
  const newest = revisions[0];
  const focus =
    revisions.find((revision) => revision.version_id === prompt.released_version_id) ?? newest;

  const detail = focus
    ? await apiRequest(`/api/v1/revisions/${encodeURIComponent(focus.version_id)}`, {
        schema: wireRevisionSchema,
      })
    : undefined;

  const base = toPrompt(prompt, names, newest);
  return {
    ...base,
    revision: focus ? revisionLabel(focus.revision_number) : '',
    provider: detail?.provider_config_id ?? '',
    providerModel: detail?.upstream_model ?? '',
    fallbackAnswer: detail?.fallback_answer ?? '',
    promptBody: detail?.body ?? '',
    revisions: revisions.map((revision) =>
      toRevision(revision, names, prompt.released_version_id ?? null),
    ),
  };
}

/**
 * Save the editor.
 *
 * **Two writes, and the split is the registry's rather than this form's.** A
 * prompt's title, purpose, access level and tags live on `prompt_property` and are
 * mutable; its body, provider binding and fallback live on a `revision` and are
 * **immutable** — the chain is append-only (ADR-0002), so "editing" a body is
 * creating the next revision. The form presents one Save; the API takes two calls,
 * in that order, because a revision naming a prompt whose title has not been
 * updated yet is a smaller inconsistency than the reverse.
 *
 * `changeSummary` is required by `RevisionCreate` and is the one field with no
 * home on `prompt_property` — it describes the *change*, which is a property of
 * the revision and of nothing else.
 */
export async function savePrompt(promptId: string, values: PromptEditorValues) {
  const parsed = promptEditorSchema.parse(values);
  const id = encodeURIComponent(promptId);

  await apiRequest(`/api/v1/prompts/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ title: parsed.title, access_level: parsed.access }),
    schema: wirePromptSchema,
  });

  return apiRequest(`/api/v1/prompts/${id}/revisions`, {
    method: 'POST',
    body: JSON.stringify({
      body: parsed.promptBody,
      change_summary: parsed.changeSummary,
      provider_config_id: parsed.provider || null,
      upstream_model: parsed.providerModel || null,
      fallback_answer: parsed.fallbackAnswer,
    }),
    schema: wireRevisionSchema,
  });
}

/**
 * Register a new prompt and its first revision.
 *
 * `modelName` is `namespace/name` on the wire, split here because that is how the
 * registry stores it — the pair is what `uq_prompt_property_model_name` arbitrates
 * and what the gateway resolves against.
 */
export async function createPrompt(values: PromptEditorValues) {
  const parsed = promptEditorSchema.parse(values);
  const [namespace, name] = parsed.modelName.split('/');

  const prompt = await apiRequest('/api/v1/prompts', {
    method: 'POST',
    body: JSON.stringify({
      namespace,
      name,
      title: parsed.title,
      access_level: parsed.access,
    }),
    schema: wirePromptSchema,
  });

  await apiRequest(`/api/v1/prompts/${encodeURIComponent(prompt.prompt_id)}/revisions`, {
    method: 'POST',
    body: JSON.stringify({
      body: parsed.promptBody,
      change_summary: parsed.changeSummary,
      provider_config_id: parsed.provider || null,
      upstream_model: parsed.providerModel || null,
      fallback_answer: parsed.fallbackAnswer,
    }),
    schema: wireRevisionSchema,
  });

  return prompt;
}

export function retirePrompt(promptId: string) {
  return apiRequest(`/api/v1/prompts/${encodeURIComponent(promptId)}/retire`, {
    method: 'POST',
    schema: wirePromptSchema,
  });
}

// ---------------------------------------------------------------------------
// Review queue and the review screen
// ---------------------------------------------------------------------------

/**
 * The reviewer's queue.
 *
 * `GET /review-tasks` answers with tasks, which name a prompt id and nothing a
 * person would recognise — so the prompts are fetched alongside and joined here.
 * One extra request for the whole queue rather than one per row.
 */
export async function getReviews(workspaceId: string) {
  const [tasks, prompts, names] = await Promise.all([
    apiRequest('/api/v1/review-tasks', { schema: z.array(wireReviewTaskSchema) }),
    apiRequest('/api/v1/prompts', { schema: z.array(wirePromptSchema) }),
    loadMemberNames(workspaceId),
  ]);

  const byId = new Map(prompts.map((prompt) => [prompt.prompt_id, prompt]));
  return tasks.map((task) => {
    const prompt = byId.get(task.prompt_id);
    return {
      id: task.review_task_id,
      promptId: task.prompt_id,
      versionId: task.version_id,
      // A task can outlive a prompt's visibility — the queue is workspace-scoped
      // and prompts are private by default — so an unresolvable title falls back
      // to the id rather than to a blank row.
      promptTitle: prompt?.title ?? task.prompt_id,
      revision: task.version_id,
      owner: prompt ? (names.get(prompt.owner_id) ?? prompt.owner_id) : '—',
      submittedAt: task.created_at,
      summary: task.kind,
      overdue: task.overdue,
      status: task.status,
    };
  });
}

/** The review screen: diff, eval evidence, cost delta, approvals and history, in one read. */
export function getReviewScreen(promptId: string, versionId: string): Promise<WireReviewScreen> {
  return apiRequest(
    `/api/v1/prompts/${encodeURIComponent(promptId)}/revisions/${encodeURIComponent(versionId)}/review`,
    { schema: wireReviewScreenSchema },
  );
}

export function submitRevision(promptId: string, versionId: string) {
  return apiRequest(
    `/api/v1/prompts/${encodeURIComponent(promptId)}/revisions/${encodeURIComponent(versionId)}/submit`,
    { method: 'POST', body: JSON.stringify({}) },
  );
}

/**
 * Record a decision.
 *
 * `acknowledgementReason` is ADR-0005's: a failing eval suite does not block
 * approval, it requires the approver to write down why they are approving anyway
 * — and that reason is stored on the approval. The review screen's
 * `acknowledgement_required` says when the field is mandatory; sending it when it
 * is not is refused, so the caller passes what the screen was told.
 */
export function decideReview(input: {
  promptId: string;
  versionId: string;
  decision: 'approve' | 'changes';
  comment?: string;
  acknowledgementReason?: string;
}) {
  const base = `/api/v1/prompts/${encodeURIComponent(input.promptId)}/revisions/${encodeURIComponent(input.versionId)}`;
  if (input.decision === 'changes') {
    return apiRequest(`${base}/request-changes`, {
      method: 'POST',
      body: JSON.stringify({ comment: input.comment ?? '' }),
    });
  }
  return apiRequest(`${base}/approve`, {
    method: 'POST',
    body: JSON.stringify({
      comment: input.comment ?? null,
      acknowledgement_reason: input.acknowledgementReason ?? null,
    }),
  });
}

// ---------------------------------------------------------------------------
// Releases
// ---------------------------------------------------------------------------

export function getReleases(promptId: string) {
  return apiRequest(`/api/v1/prompts/${encodeURIComponent(promptId)}/releases`, {
    schema: z.array(wireReleaseSchema),
  });
}

/**
 * Release, restore, or break the glass.
 *
 * The three are separate endpoints rather than a `kind` field, because they are
 * separate **permissions** — `release.create`, and `release.break_glass` which is
 * its own escape hatch precisely so that not everybody holds it (A-009). The form
 * offers three actions; the API keeps them apart all the way down.
 *
 * `expected_current_version_id` is the compare-and-set: it is what stops two
 * people releasing different revisions at the same moment and one of them winning
 * silently. Omitted here only when the caller does not know the current pointer.
 */
export function releaseRevision(promptId: string, values: ReleaseFormValues, expectedCurrent?: string | null) {
  const parsed = releaseFormSchema.parse(values);
  const base = `/api/v1/prompts/${encodeURIComponent(promptId)}/releases`;

  if (parsed.action === 'breakGlass') {
    return apiRequest(`${base}/break-glass`, {
      method: 'POST',
      body: JSON.stringify({
        version_id: parsed.targetRevision,
        expected_current_version_id: expectedCurrent ?? null,
        reason: parsed.reason,
      }),
      schema: wireReleaseSchema,
    });
  }

  return apiRequest(base, {
    method: 'POST',
    body: JSON.stringify({
      version_id: parsed.targetRevision,
      // A restore is an ordinary release of an older approved revision — the same
      // decision, recorded with its own kind so the log can say which it was.
      kind: parsed.action === 'restore' ? 'restore' : 'release',
      expected_current_version_id: expectedCurrent ?? null,
      reason: parsed.reason || null,
    }),
    schema: wireReleaseSchema,
  });
}

export function withdrawRelease(promptId: string, reason: string) {
  return apiRequest(`/api/v1/prompts/${encodeURIComponent(promptId)}/releases/withdraw`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
    schema: wireReleaseSchema,
  });
}

// ---------------------------------------------------------------------------
// Providers
// ---------------------------------------------------------------------------

/**
 * Every configured provider, each with its model catalogue.
 *
 * One request per provider for the catalogue, which is a fan-out — bounded by the
 * number of providers a workspace configures, which is a handful and is not a
 * function of traffic. The alternative is a composite endpoint nobody else needs.
 */
export async function getProviders() {
  const providers = await apiRequest('/api/v1/providers', { schema: z.array(wireProviderSchema) });
  const catalogues = await Promise.all(
    providers.map((provider) =>
      apiRequest(`/api/v1/providers/${encodeURIComponent(provider.provider_config_id)}/models`, {
        schema: z.array(wireModelSchema),
      }).catch(() => []),
    ),
  );
  return providers.map((provider, index) =>
    toProvider(
      provider,
      // A catalogue read that failed resolves to `[]` above, so the provider still
      // renders — with no models and its verification state showing why.
      (catalogues[index] ?? []).filter((model) => model.available).map((model) => model.model_id),
    ),
  );
}

/**
 * Configure a provider.
 *
 * The credential is **write-only across the whole seam** — no route reads one back
 * and none ever may (A-113). What comes back is `credential_last_four`, which is
 * the only credential-derived value that crosses.
 */
export async function saveProvider(values: ProviderFormValues) {
  const parsed = providerFormSchema.parse(values);
  const provider = await apiRequest('/api/v1/providers', {
    method: 'POST',
    body: JSON.stringify({
      display_name: parsed.provider,
      base_url: parsed.baseUrl,
      credential: parsed.credential,
    }),
    schema: wireProviderSchema,
  });

  // Verification is a separate call because it reaches the provider's API, which
  // can fail for reasons that have nothing to do with the configuration being
  // wrong — so it must not take the create down with it.
  await apiRequest(`/api/v1/providers/${encodeURIComponent(provider.provider_config_id)}/verify`, {
    method: 'POST',
    body: JSON.stringify({}),
  }).catch(() => undefined);

  return provider;
}

// ---------------------------------------------------------------------------
// Call records — ADR-0055
// ---------------------------------------------------------------------------

/**
 * What one prompt has actually served. **Metadata only; there is no body here.**
 *
 * ADR-0018 gives `ledger.call_body` no read path and says of the rest that
 * *"metadata is unaffected ... it has readers"*. ADR-0055 built this reader, in
 * prompt-registry rather than in call-ledger, behind `prompt.read` — which is why
 * this is a per-prompt call and there is no workspace-wide list: every record
 * names a prompt id, and a flat list would say that a private prompt exists.
 */
export async function getCallRecords(promptId: string, promptTitle: string) {
  const records = await apiRequest(
    `/api/v1/prompts/${encodeURIComponent(promptId)}/call-records`,
    { schema: z.array(wireCallRecordSchema) },
  );
  return records.map((record) => toCallRecord(record, promptTitle));
}

// ---------------------------------------------------------------------------
// Evaluation
// ---------------------------------------------------------------------------

export function startEvaluation(promptId: string, versionId: string) {
  return apiRequest(`/api/v1/prompts/${encodeURIComponent(promptId)}/eval-runs`, {
    method: 'POST',
    body: JSON.stringify({ version_id: versionId }),
  });
}
