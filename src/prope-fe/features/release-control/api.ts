import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { applyMockRelease, promptKeys, readMockPromptsSnapshot } from '@/features/preservation/queries';
import { getRestoreCandidates, releaseDecisionFormSchema, releaseWorkspaceSchema, restoreDecisionFormSchema, type ReleaseWorkspace } from '@/features/release-control/types';
import { readRecordedApproval, recordBreakGlassFollowUp, reviewKeys } from '@/features/review/api';

const wait = () => new Promise((resolve) => window.setTimeout(resolve, 380));
const workspaces = new Map<string, ReleaseWorkspace>();

function createWorkspace(promptId: string) {
  const prompt = readMockPromptsSnapshot().find((item) => item.id === promptId);
  const approval = readRecordedApproval(promptId);
  const releases = prompt?.releasedVersionId && prompt.releasedRevision ? [
    { id: `${promptId}-release-${prompt.releasedRevision}`, revisionId: prompt.releasedVersionId, revisionNumber: prompt.releasedRevision, versionId: prompt.releasedVersionId, releasedBy: 'An Trần', releasedAt: '2026-08-09T08:15:00.000Z', reason: 'Bản ổn định cho luồng đang sử dụng.', current: true, kind: 'release' as const, approvalId: `${promptId}-approval-${prompt.releasedRevision}` },
    ...(prompt.releasedRevision > 1 ? [{ id: `${promptId}-release-1`, revisionId: `${promptId}-revision-1`, revisionNumber: 1, versionId: `${promptId}-revision-1`, releasedBy: 'An Trần', releasedAt: '2026-08-04T04:00:00.000Z', reason: 'Release đầu tiên.', current: false, kind: 'release' as const, approvalId: `${promptId}-approval-1` }] : []),
  ] : [];
  return releaseWorkspaceSchema.parse({
    promptId, permission: promptId === 'release-denied' ? 'denied' : 'release', candidateRevisionId: prompt?.currentVersionId ?? `${promptId}-revision-1`, candidateRevisionNumber: prompt?.currentRevision ?? 1,
    modelName: prompt?.modelName ?? 'research/customer-insight-summary', usageContext: 'OpenAI-compatible gateway · production · single released pointer',
    approverName: approval?.reviewerName ?? 'Minh Phạm', approvedAt: approval?.decidedAt ?? '2026-08-11T03:10:00.000Z', approvalReason: approval?.reason ?? 'Failure đã được xem xét; output mới xử lý thiếu bằng chứng an toàn hơn.',
    releases,
  });
}

async function readWorkspace(promptId: string) {
  await wait();
  if (!promptId || promptId === 'release-error') throw new Error('RELEASE_NOT_FOUND');
  const workspace = workspaces.get(promptId) ?? createWorkspace(promptId);
  workspaces.set(promptId, workspace);
  return releaseWorkspaceSchema.parse(workspace);
}

async function releaseApproved(input: { promptId: string; reason: string; approved: boolean; breakGlass: boolean }) {
  await wait();
  const values = releaseDecisionFormSchema.parse(input);
  const workspace = workspaces.get(input.promptId) ?? createWorkspace(input.promptId);
  if ((!input.approved && !values.breakGlass) || workspace.permission !== 'release') throw new Error('RELEASE_NOT_ALLOWED');
  const releases = workspace.releases.map((item) => ({ ...item, current: false }));
  const updated = releaseWorkspaceSchema.parse({ ...workspace, releases: [{ id: `${input.promptId}-release-${Date.now()}`, revisionId: workspace.candidateRevisionId, revisionNumber: workspace.candidateRevisionNumber, versionId: workspace.candidateRevisionId, releasedBy: 'Linh Nguyễn', releasedAt: new Date().toISOString(), reason: values.reason, current: true, kind: values.breakGlass ? 'breakGlass' : 'release', approvalId: values.breakGlass ? null : `${input.promptId}-approval-${workspace.candidateRevisionNumber}` }, ...releases] });
  workspaces.set(input.promptId, updated);
  applyMockRelease(input.promptId, workspace.candidateRevisionNumber, workspace.candidateRevisionId);
  if (values.breakGlass) recordBreakGlassFollowUp(input.promptId);
  return updated;
}

async function restoreApproved(input: { promptId: string; revisionId: string; reason: string }) {
  await wait();
  const values = restoreDecisionFormSchema.parse(input);
  const workspace = workspaces.get(input.promptId) ?? createWorkspace(input.promptId);
  const target = getRestoreCandidates(workspace).find((item) => item.revisionId === values.revisionId);
  if (!target || workspace.permission !== 'release') throw new Error('RESTORE_NOT_ALLOWED');
  const releases = workspace.releases.map((item) => ({ ...item, current: false }));
  const updated = releaseWorkspaceSchema.parse({ ...workspace, releases: [{ id: `${input.promptId}-restore-${Date.now()}`, revisionId: target.revisionId, revisionNumber: target.revisionNumber, versionId: target.versionId, releasedBy: 'Linh Nguyễn', releasedAt: new Date().toISOString(), reason: values.reason, current: true, kind: 'restore', approvalId: target.approvalId }, ...releases] });
  workspaces.set(input.promptId, updated);
  applyMockRelease(input.promptId, target.revisionNumber, target.versionId);
  return updated;
}

export const releaseKeys = { detail: (promptId: string) => ['release-workspace', promptId] as const };
export const releaseOptions = (promptId: string) => queryOptions({ queryKey: releaseKeys.detail(promptId), queryFn: () => readWorkspace(promptId) });

function useReleaseMutation<TInput>(mutationFn: (input: TInput) => Promise<ReleaseWorkspace>) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn, onSuccess: (workspace) => { queryClient.setQueryData(releaseKeys.detail(workspace.promptId), workspace); void queryClient.invalidateQueries({ queryKey: promptKeys.all }); void queryClient.invalidateQueries({ queryKey: promptKeys.detail(workspace.promptId) }); void queryClient.invalidateQueries({ queryKey: ['trusted-registry'] }); void queryClient.invalidateQueries({ queryKey: reviewKeys.all }); } });
}

export function useReleaseApprovedRevision() { return useReleaseMutation(releaseApproved); }
export function useRestoreApprovedRevision() { return useReleaseMutation(restoreApproved); }
