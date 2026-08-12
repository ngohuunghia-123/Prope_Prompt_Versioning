import type {
  WireCallRecord,
  WireProvider,
  WirePrompt,
  WireRevision,
  WireRevisionSummary,
} from '@/features/prompt-lifecycle/wire';
import type {
  CallRecord,
  LifecycleStatus,
  Prompt,
  Provider,
  Revision,
} from '@/features/prompt-lifecycle/types';

/**
 * The one place the API's shapes become the shapes the screens read.
 *
 * Everything here is a pure function of a wire object plus, where a name is
 * wanted, a lookup the caller already has. No fetching, so the mapping can be
 * reasoned about and tested without a server.
 */

/**
 * Resolve a `usr_...` id to something a person recognises.
 *
 * **The API returns ids, and only one endpoint turns them into names**:
 * `GET /workspaces/{id}/members`, which is gated on `workspace.manage_members`
 * and therefore refused to everybody but an Admin. So a name is a *best effort*
 * and the id is the truth — a screen that showed a blank where it could not
 * resolve one would be hiding the fact that the record exists.
 *
 * Falls back to the raw id rather than to "Unknown", because the id is what an
 * Admin would search for when somebody asks who made a change.
 */
export function displayUser(userId: string | null | undefined, names: ReadonlyMap<string, string>): string {
  if (!userId) return '—';
  return names.get(userId) ?? userId;
}

/**
 * The status a screen shows for a prompt, derived rather than stored.
 *
 * **The backend keeps two facts and the UI wants one.** `prompt_property.status`
 * is `active | retired` — the shelf the revisions sit on (A-049) — and
 * `released_version_id` says whether anything of this prompt is serving traffic.
 * Revision status (`Draft | In review | Approved`) is a third fact, on a different
 * table, and the list endpoint does not carry it.
 *
 * So the rule is:
 *
 * - `retired` wins over everything. It is terminal; nothing un-retires a prompt.
 * - a released pointer means `inUse`, whatever the newest revision is doing.
 * - otherwise fall back to the newest revision's own status when the caller has
 *   it — the detail page does, the registry list does not — and to `draft` when
 *   it does not.
 *
 * **The list is therefore coarser than the detail page, deliberately.** Refining
 * it would mean one revisions request per row, which is a fan-out on the screen
 * most likely to be open, to sharpen a label. The detail page pays for the
 * precision at the point somebody asks for it.
 */
export function lifecycleStatus(
  prompt: WirePrompt,
  newestRevision?: WireRevisionSummary,
): LifecycleStatus {
  if (prompt.status === 'retired') return 'retired';
  if (prompt.released_version_id) return 'inUse';
  if (newestRevision?.status === 'In review') return 'inReview';
  if (newestRevision?.status === 'Approved') return 'approved';
  return 'draft';
}

/** `r12`, from `revision_number`. The `r` is display; the number is the fact. */
export function revisionLabel(revisionNumber: number): string {
  return `r${revisionNumber}`;
}

export function toPrompt(
  prompt: WirePrompt,
  names: ReadonlyMap<string, string>,
  newestRevision?: WireRevisionSummary,
): Prompt {
  return {
    id: prompt.prompt_id,
    title: prompt.title,
    modelName: prompt.model_name,
    owner: displayUser(prompt.owner_id, names),
    ownerId: prompt.owner_id,
    access: prompt.access_level,
    status: lifecycleStatus(prompt, newestRevision),
    // The released *pointer* is a version id, not a number, and the list endpoint
    // carries no revision numbers — so this is empty until the detail page loads
    // the chain and can say which `r` the pointer names.
    revision: newestRevision ? revisionLabel(newestRevision.revision_number) : '',
    releasedVersionId: prompt.released_version_id ?? null,
    updatedAt: prompt.updated_at,
    tags: prompt.tags,
    purpose: prompt.purpose,
  };
}

export function toRevision(
  revision: WireRevisionSummary,
  names: ReadonlyMap<string, string>,
  releasedVersionId: string | null,
): Revision {
  return {
    id: revision.version_id,
    number: revisionLabel(revision.revision_number),
    revisionNumber: revision.revision_number,
    // `In use` is not a stored revision status (A-065) — it is the released
    // pointer pointing here, which is why it is computed rather than read.
    status:
      revision.version_id === releasedVersionId
        ? 'inUse'
        : revision.status === 'In review'
          ? 'inReview'
          : revision.status === 'Approved'
            ? 'approved'
            : 'draft',
    author: displayUser(revision.author_id, names),
    createdAt: revision.created_at,
    summary: revision.change_summary,
    // **Absent, not zero.** Eval results live on runs, and a run belongs to a
    // revision *and a suite* — there may be none, or several. The review screen
    // carries them for the one revision under review; the chain does not, and a
    // `0/0` here would read as "it failed everything" rather than "nobody asked".
    evalPassed: undefined,
    evalTotal: undefined,
    cost: undefined,
  };
}

export function toProvider(provider: WireProvider, models: readonly string[]): Provider {
  return {
    id: provider.provider_config_id,
    name: provider.display_name,
    models: [...models],
    // `verification_status` is the provider's own answer to "did the credential
    // work the last time we asked". Anything but a clean verification is
    // `attention`, because the screen's job is to say whether somebody needs to
    // look — not to reproduce a four-value enum nobody has a legend for.
    state: provider.verification_status === 'verified' ? 'connected' : 'attention',
    verificationStatus: provider.verification_status,
    verificationError: provider.verification_error ?? null,
    credentialLastFour: provider.credential_last_four ?? null,
    updatedAt: provider.updated_at,
  };
}

export function toCallRecord(record: WireCallRecord, promptTitle: string): CallRecord {
  const input = record.input_tokens ?? 0;
  const output = record.output_tokens ?? 0;
  return {
    id: record.call_id,
    promptTitle,
    versionId: record.version_id ?? '—',
    // Which integration called, not who. `actor_id` is deliberately not in the
    // read at all (ADR-0055).
    consumer: record.consumer_key_id ?? record.source,
    timestamp: record.created_at,
    tokens: input + output,
    // A string on the wire and a string here. `cost_status` says whether to
    // believe it: `unpriced` means no price row covered this call yet, and
    // summing those as zero would under-report.
    cost: record.cost,
    costStatus: record.cost_status,
    currency: record.currency ?? null,
    outcome: record.fallback ? 'fallback' : record.outcome === 'ok' ? 'success' : 'error',
  };
}

/** The prompt body, which lives on a revision rather than on the prompt. */
export function revisionBody(revision: WireRevision | undefined): string {
  return revision?.body ?? '';
}
