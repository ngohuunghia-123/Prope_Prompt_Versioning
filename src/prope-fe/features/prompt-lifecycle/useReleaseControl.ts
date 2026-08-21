import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { notificationKeys } from '@/features/notifications/queries';
import { isApiError } from '@/lib/apiClient';
import { lifecycleKeys } from '@/features/prompt-lifecycle/queries';
import {
  approveRevision,
  breakGlassRelease,
  createRelease,
  getReleases,
  getReviewScreen,
  requestChanges,
  submitRevision,
  withdrawRelease,
} from '@/features/prompt-lifecycle/releaseApi';

/**
 * One revision's position on the release path, and the four acts that move it.
 *
 * **Every mutation invalidates the prompt itself, not just this screen.** The
 * released pointer is a field on the prompt row, so a release that refreshed
 * only the review screen would leave the rail, the header badge and the search
 * index panel all showing the previous state until a reload.
 */

/**
 * The refusal codes this screen expects and explains, as opposed to failing.
 *
 * Each one is a legitimate answer rather than a fault: the reader holds a
 * different role, or another admin released first, or the evidence is stale and
 * the approval needs a written acknowledgement.
 */
export const EXPECTED_REFUSALS = new Set([
  'release_revision_not_approved',
  'release_no_approval_recorded',
  'release_acknowledgement_required',
  'release_pointer_conflict',
  'release_illegal_transition',
  'release_review_already_open',
  'release_nothing_released',
  'release_not_previously_released',
  'release_reason_required',
  'forbidden',
]);

export interface ReleaseRefusal {
  code: string;
  message: string;
}

function refusalOf(error: unknown): ReleaseRefusal | null {
  if (!isApiError(error)) return null;
  return { code: error.code, message: error.message };
}

export function useReleaseControl(promptId: string, versionId: string) {
  const client = useQueryClient();
  const [refusal, setRefusal] = useState<ReleaseRefusal | null>(null);

  const screen = useQuery({
    queryKey: lifecycleKeys.releaseScreen(promptId, versionId),
    queryFn: () => getReviewScreen(promptId, versionId),
    enabled: Boolean(promptId && versionId),
  });

  const history = useQuery({
    queryKey: lifecycleKeys.releases(promptId),
    queryFn: () => getReleases(promptId),
    enabled: Boolean(promptId),
  });

  // A write changed the released pointer, the revision status, or both. Refresh
  // the prompt as well as this screen — see the note at the top of the file.
  const settle = async () => {
    setRefusal(null);
    await Promise.all([
      client.invalidateQueries({ queryKey: lifecycleKeys.releaseScreen(promptId, versionId) }),
      client.invalidateQueries({ queryKey: lifecycleKeys.releases(promptId) }),
      client.invalidateQueries({ queryKey: lifecycleKeys.prompt(promptId) }),
      client.invalidateQueries({ queryKey: lifecycleKeys.prompts }),
      client.invalidateQueries({ queryKey: lifecycleKeys.promptIndex(promptId) }),
      client.invalidateQueries({ queryKey: notificationKeys.all }),
    ]);
  };

  const onError = (error: unknown) => setRefusal(refusalOf(error));

  const submit = useMutation({
    mutationFn: () => submitRevision(promptId, versionId),
    onSuccess: settle,
    onError,
  });

  const approve = useMutation({
    mutationFn: (input: { comment?: string; acknowledgementReason?: string }) =>
      approveRevision(promptId, versionId, input),
    onSuccess: settle,
    onError,
  });

  const reject = useMutation({
    mutationFn: (comment: string) => requestChanges(promptId, versionId, comment),
    onSuccess: settle,
    onError,
  });

  const release = useMutation({
    mutationFn: (input: { kind?: 'release' | 'restore'; reason?: string }) =>
      createRelease(promptId, {
        versionId,
        kind: input.kind,
        // Sent from the screen's own read, so a pointer that moved underneath
        // this reader is refused rather than overwritten.
        expectedCurrentVersionId: screen.data?.released_version_id ?? null,
        reason: input.reason,
      }),
    onSuccess: settle,
    onError,
  });

  const withdraw = useMutation({
    mutationFn: (reason: string) => withdrawRelease(promptId, reason),
    onSuccess: settle,
    onError,
  });

  const breakGlass = useMutation({
    mutationFn: (reason: string) =>
      breakGlassRelease(promptId, {
        versionId,
        reason,
        expectedCurrentVersionId: screen.data?.released_version_id ?? null,
      }),
    onSuccess: settle,
    onError,
  });

  const working =
    submit.isPending ||
    approve.isPending ||
    reject.isPending ||
    release.isPending ||
    withdraw.isPending ||
    breakGlass.isPending;

  return {
    screen,
    history,
    submit,
    approve,
    reject,
    release,
    withdraw,
    breakGlass,
    working,
    refusal,
    clearRefusal: () => setRefusal(null),
  };
}
