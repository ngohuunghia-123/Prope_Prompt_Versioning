import { promptDraftSchema, promptDetailSchema, revisionSchema, type PromptDetail, type PromptDraft, type Revision } from '@/features/prompt-lifecycle/types';
import type { RouterComboEntry } from '@/features/prompt-lifecycle/routerComboTypes';

const wait = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

/**
 * The draft layer for prompt versions.
 *
 * The registry has no draft endpoints yet, so this module is the mock seam:
 * drafts live in in-session stores and every function below is shaped like the
 * REST call that will replace it (`POST …/revisions/{id}/drafts`,
 * `PATCH …/drafts/{id}`, `POST …/drafts/{id}/promote`). Swapping in the real
 * backend means replacing the bodies, not the call sites.
 *
 * Two stores keep the overlay honest:
 * - `draftsByPrompt` — editable clones, keyed by prompt.
 * - `overlayByPrompt` — revisions CREATED by promotion (drafts consumed into
 *   versions) plus the ids of previously-live versions those promotions
 *   retired. `withDraftOverlay` folds both into any `PromptDetail` so the
 *   version tree, the editor and the gate all read one consistent history.
 */
const draftsByPrompt = new Map<string, PromptDraft[]>();
const overlayByPrompt = new Map<string, { extraRevisions: Revision[]; retiredVersionIds: Set<string> }>();

// One seeded draft so the expandable tree and the promote flow are reachable
// without pressing anything first. It clones the prompt's published r12.
function seedDemoDrafts() {
  if (draftsByPrompt.size > 0) return;
  draftsByPrompt.set('checkout-assistant', [
    promptDraftSchema.parse({
      id: 'draft_checkout_12_1',
      promptId: 'checkout-assistant',
      parentRevisionId: 'rev_checkout_12',
      name: 'Draft',
      createdAt: '2026-08-12T09:30:00+07:00',
      updatedAt: '2026-08-12T09:30:00+07:00',
      author: 'Linh Nguyễn',
      promptBody: `<system>\nYou are the checkout assistant. Follow the approved checkout policy.\n</system>\n\n<context>\nCustomer: {{customer_name}}\nQuestion: {{question}}\n</context>\n\n<instructions>\nReturn concise guidance and emit the required handoff object.\nIf the cart total exceeds the customer's stored limit, ask for confirmation before continuing.\n</instructions>\n\n<output_format>\nReturn valid JSON matching the approved schema.\n</output_format>`,
      summary: 'Add spend-limit confirmation before checkout continues.',
      tags: ['production'],
    }),
  ]);
}

function draftsOf(promptId: string): PromptDraft[] {
  seedDemoDrafts();
  let drafts = draftsByPrompt.get(promptId);
  if (!drafts) {
    drafts = [];
    draftsByPrompt.set(promptId, drafts);
  }
  return drafts;
}

function overlayOf(promptId: string): { extraRevisions: Revision[]; retiredVersionIds: Set<string> } {
  let overlay = overlayByPrompt.get(promptId);
  if (!overlay) {
    overlay = { extraRevisions: [], retiredVersionIds: new Set<string>() };
    overlayByPrompt.set(promptId, overlay);
  }
  return overlay;
}

/** Folds promoted revisions and drafts into a loaded prompt detail. Drafts
 * whose parent version is no longer in the history are dropped rather than
 * rendered orphaned. */
export function withDraftOverlay(detail: PromptDetail): PromptDetail {
  const overlay = overlayByPrompt.get(detail.id);
  const extra = overlay?.extraRevisions ?? [];
  const retired = overlay?.retiredVersionIds ?? new Set<string>();
  const merged = [...extra, ...detail.revisions]
    .map((revision) => (retired.has(revision.id) ? { ...revision, status: 'retired' as const } : revision))
    .sort((a, b) => (revisionNumber(b) - revisionNumber(a)));
  const drafts = draftsOf(detail.id).filter((draft) => merged.some((revision) => revision.id === draft.parentRevisionId));
  return promptDetailSchema.parse({ ...detail, revisions: merged, drafts });
}

function revisionNumber(revision: Revision): number {
  return Number.parseInt(revision.number.replace(/^r/, ''), 10) || 0;
}

/** The publish gate (requirement 1): a new version may only be created while
 * the prompt's newest version is the published one. Revisions arrive
 * newest-first from both the mock and the real mapping. */
export function latestVersionIsPublished(revisions: Revision[]): boolean {
  return revisions[0]?.status === 'inUse';
}

export function nextRevisionNumber(revisions: Revision[]): number {
  return revisions.reduce((max, revision) => Math.max(max, revisionNumber(revision)), 0) + 1;
}

/** Thrown by `promoteDraft` when the gate is closed — a backstop behind the
 * disabled button, so a stale screen cannot promote past an unpublished tip. */
export class DraftGateError extends Error {
  constructor() {
    super('latest-version-not-published');
    this.name = 'DraftGateError';
  }
}

export interface DraftUpdateValues {
  promptBody: string;
  providerConfigId?: string;
  upstreamModel?: string;
  routeComboId?: string;
  routeComboName?: string;
  route?: RouterComboEntry[];
  tags?: string[];
  summary?: string;
}

function cloneDraftName(parentRevisionId: string, existing: PromptDraft[]): string {
  const count = existing.filter((draft) => draft.parentRevisionId === parentRevisionId).length;
  return count === 0 ? 'Draft' : `Draft ${count + 1}`;
}

/** Clone a saved version into a new editable draft under it. */
export async function createDraft(input: { promptId: string; source: Revision }): Promise<PromptDraft> {
  await wait(260);
  const drafts = draftsOf(input.promptId);
  const now = new Date().toISOString();
  const draft = promptDraftSchema.parse({
    id: `draft_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`,
    promptId: input.promptId,
    parentRevisionId: input.source.id,
    name: cloneDraftName(input.source.id, drafts),
    createdAt: now,
    updatedAt: now,
    author: input.source.author,
    promptBody: input.source.promptBody,
    summary: input.source.summary,
    providerConfigId: input.source.providerConfigId,
    upstreamModel: input.source.upstreamModel,
    routeComboId: input.source.routeComboId,
    routeComboName: input.source.routeComboName,
    route: [...input.source.route],
    parameters: { ...input.source.parameters },
    tags: [...input.source.tags],
  });
  // Newest draft first, matching how the version list itself reads.
  drafts.unshift(draft);
  return draft;
}

/** Save edits into a draft in place. Drafts are mutable — that is the whole
 * difference between a draft and a version. */
export async function updateDraft(input: { promptId: string; draftId: string; values: DraftUpdateValues }): Promise<PromptDraft> {
  await wait(260);
  const drafts = draftsOf(input.promptId);
  const draft = drafts.find((candidate) => candidate.id === input.draftId);
  if (!draft) throw new Error('draft-not-found');
  const next = promptDraftSchema.parse({
    ...draft,
    promptBody: input.values.promptBody,
    providerConfigId: input.values.providerConfigId ?? draft.providerConfigId,
    upstreamModel: input.values.upstreamModel ?? draft.upstreamModel,
    routeComboId: input.values.routeComboId ?? draft.routeComboId,
    routeComboName: input.values.routeComboName ?? draft.routeComboName,
    route: input.values.route ?? draft.route,
    tags: input.values.tags ?? draft.tags,
    summary: input.values.summary ?? draft.summary,
    updatedAt: new Date().toISOString(),
  });
  drafts.splice(drafts.indexOf(draft), 1, next);
  return next;
}

export async function renameDraft(input: { promptId: string; draftId: string; name: string }): Promise<PromptDraft> {
  await wait(180);
  const drafts = draftsOf(input.promptId);
  const draft = drafts.find((candidate) => candidate.id === input.draftId);
  if (!draft) throw new Error('draft-not-found');
  const next = promptDraftSchema.parse({ ...draft, name: input.name, updatedAt: new Date().toISOString() });
  drafts.splice(drafts.indexOf(draft), 1, next);
  return next;
}

export interface PromoteDraftResult {
  revisionId: string;
  revisionNumber: string;
}

/** Render a draft with the components built for revisions: the same metadata
 * and binding surfaces, stamped with the parent version's number and a `draft`
 * status so no badge lies about what it is. */
export function draftToDisplayRevision(draft: PromptDraft, parent: Revision): Revision {
  return revisionSchema.parse({
    id: draft.id,
    number: parent.number,
    status: 'draft',
    author: draft.author,
    createdAt: draft.createdAt,
    summary: draft.summary || draft.name,
    evalPassed: 0,
    evalTotal: 1,
    cost: 0,
    promptBody: draft.promptBody,
    providerConfigId: draft.providerConfigId,
    upstreamModel: draft.upstreamModel,
    routeComboId: draft.routeComboId,
    routeComboName: draft.routeComboName,
    route: [...draft.route],
    parameters: { ...draft.parameters },
    tags: [...draft.tags],
  });
}

/** Consume a draft into the prompt's next version, published immediately. The
 * previously live version — mock pointer or an earlier promotion — is retired,
 * which is what the released-pointer move means on the wire. */
export async function promoteDraft(input: { promptId: string; draftId: string; revisions: Revision[] }): Promise<PromoteDraftResult> {
  await wait(320);
  if (!latestVersionIsPublished(input.revisions)) throw new DraftGateError();
  const drafts = draftsOf(input.promptId);
  const draft = drafts.find((candidate) => candidate.id === input.draftId);
  if (!draft) throw new Error('draft-not-found');
  const overlay = overlayOf(input.promptId);
  const next = nextRevisionNumber(input.revisions);
  const revision = revisionSchema.parse({
    id: `rev_${input.promptId}_${next}_${Date.now().toString(36)}`,
    number: `r${next}`,
    status: 'inUse',
    author: draft.author,
    createdAt: new Date().toISOString(),
    summary: draft.summary || `Promoted from draft “${draft.name}”.`,
    evalPassed: 0,
    evalTotal: 1,
    cost: 0,
    promptBody: draft.promptBody,
    providerConfigId: draft.providerConfigId,
    upstreamModel: draft.upstreamModel,
    routeComboId: draft.routeComboId,
    routeComboName: draft.routeComboName,
    route: [...draft.route],
    parameters: { ...draft.parameters },
    tags: [...draft.tags],
  });
  for (const existing of input.revisions) {
    if (existing.status === 'inUse') overlay.retiredVersionIds.add(existing.id);
  }
  overlay.extraRevisions.unshift(revision);
  drafts.splice(drafts.indexOf(draft), 1);
  return { revisionId: revision.id, revisionNumber: revision.number };
}
