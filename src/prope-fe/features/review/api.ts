import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { readEvaluationReviewSummary } from '@/features/evaluation/api';
import { applyMockPromptStatus, promptKeys, readMockPromptsSnapshot } from '@/features/preservation/queries';
import { reviewDecisionFormSchema, reviewTaskListSchema, reviewWorkspaceSchema, type ReviewDecisionFormValues, type ReviewWorkspace } from '@/features/review/types';

const wait = () => new Promise((resolve) => window.setTimeout(resolve, 360));
const workspaces = new Map<string, ReviewWorkspace>();
const breakGlassFollowUps = new Map<string, {
  id: string;
  promptId: string;
  promptTitle: string;
  ownerName: string;
  revisionNumber: number;
  versionId: string;
  createdAt: string;
  dueAt: string;
  kind: 'breakGlassFollowUp';
}>();

function createWorkspace(promptId: string) {
  const prompt = readMockPromptsSnapshot().find((item) => item.id === promptId);
  const evaluationSuites = readEvaluationReviewSummary(promptId);
  return reviewWorkspaceSchema.parse({
    promptId, promptTitle: prompt?.title ?? 'Tóm tắt phỏng vấn khách hàng', permission: promptId === 'review-denied' ? 'denied' : 'review',
    revisionId: prompt?.currentVersionId ?? `${promptId}-revision-3`, revisionNumber: prompt?.currentRevision ?? 3, changeSummary: 'Làm rõ cách tách bằng chứng khỏi suy luận',
    authorName: prompt?.ownerName ?? 'Linh Nguyễn', submittedAt: prompt?.updatedAt ?? '2026-08-11T02:20:00.000Z',
    beforeContent: 'Tóm tắt ghi chú và nêu các phát hiện chính.',
    candidateContent: prompt?.content ?? 'Nhóm phát hiện theo nhu cầu, nỗi đau và hành vi. Mỗi kết luận phải có bằng chứng trực tiếp; nếu thiếu, trả về INSUFFICIENT_EVIDENCE.',
    modelName: prompt?.modelName ?? 'research/customer-insight-summary', usageContext: `${prompt?.providerName ?? 'OpenAI-compatible gateway'} · single released pointer`,
    fallbackAnswer: prompt?.fallbackAnswer ?? '',
    suites: evaluationSuites.length ? evaluationSuites : [
      { name: 'accuracy', version: 2, modality: 'text', passed: 9, failed: 1, errored: 0, costDelta: 29.2 },
      { name: 'format', version: 1, modality: 'structured', passed: 10, failed: 0, errored: 0, costDelta: 8.4 },
    ],
    requiresAcknowledgement: true, decision: null,
  });
}

async function readWorkspace(promptId: string) {
  await wait();
  if (!promptId || promptId === 'review-error') throw new Error('REVIEW_NOT_FOUND');
  const existing = workspaces.get(promptId);
  const workspace = existing?.decision ? existing : createWorkspace(promptId);
  workspaces.set(promptId, workspace);
  return reviewWorkspaceSchema.parse(workspace);
}

async function recordDecision(input: ReviewDecisionFormValues & { promptId: string }) {
  await wait();
  const values = reviewDecisionFormSchema.parse(input);
  const workspace = workspaces.get(input.promptId) ?? createWorkspace(input.promptId);
  if (workspace.permission !== 'review') throw new Error('REVIEW_FORBIDDEN');
  const updated = reviewWorkspaceSchema.parse({ ...workspace, decision: { status: values.decision, reason: values.reason, comment: values.comment, reviewerName: 'Minh Phạm', decidedAt: new Date().toISOString() } });
  workspaces.set(input.promptId, updated);
  breakGlassFollowUps.delete(input.promptId);
  const prompt = applyMockPromptStatus(input.promptId, values.decision === 'approved' ? 'approved' : 'draft');
  return { workspace: updated, prompt };
}

async function readReviewTasks() {
  await wait();
  const tasks = readMockPromptsSnapshot().filter((prompt) => prompt.status === 'inReview').map((prompt) => ({
    id: `review-${prompt.currentVersionId}`, promptId: prompt.id, promptTitle: prompt.title, ownerName: prompt.ownerName,
    revisionNumber: prompt.currentRevision, versionId: prompt.currentVersionId, createdAt: prompt.updatedAt, dueAt: null, kind: 'revisionReview' as const,
  }));
  const seededFollowUp = workspaces.get('customer-insight-summary')?.decision ? [] : [{ id: 'break-glass-follow-up', promptId: 'customer-insight-summary', promptTitle: 'Tóm tắt phỏng vấn khách hàng', ownerName: 'Linh Nguyễn', revisionNumber: 3, versionId: 'customer-insight-summary-revision-3', createdAt: '2026-08-10T02:00:00.000Z', dueAt: '2026-08-11T02:00:00.000Z', kind: 'breakGlassFollowUp' as const }];
  return reviewTaskListSchema.parse([...tasks, ...seededFollowUp, ...breakGlassFollowUps.values()]);
}

export function recordBreakGlassFollowUp(promptId: string) {
  const prompt = readMockPromptsSnapshot().find((item) => item.id === promptId);
  if (!prompt) return;
  const createdAt = new Date();
  const dueAt = new Date(createdAt.getTime() + 24 * 60 * 60 * 1000);
  breakGlassFollowUps.set(promptId, {
    id: `break-glass-${prompt.currentVersionId}`,
    promptId,
    promptTitle: prompt.title,
    ownerName: prompt.ownerName,
    revisionNumber: prompt.currentRevision,
    versionId: prompt.currentVersionId,
    createdAt: createdAt.toISOString(),
    dueAt: dueAt.toISOString(),
    kind: 'breakGlassFollowUp',
  });
}

export function readRecordedApproval(promptId: string) {
  const decision = workspaces.get(promptId)?.decision;
  return decision?.status === 'approved' ? decision : null;
}

export const reviewKeys = { all: ['review-tasks'] as const, detail: (promptId: string) => ['review-workspace', promptId] as const };
export const reviewOptions = (promptId: string) => queryOptions({ queryKey: reviewKeys.detail(promptId), queryFn: () => readWorkspace(promptId) });
export const reviewTaskOptions = queryOptions({ queryKey: reviewKeys.all, queryFn: readReviewTasks });

export function useReviewDecision() {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: recordDecision, onSuccess: ({ workspace, prompt }) => {
    queryClient.setQueryData(reviewKeys.detail(workspace.promptId), workspace);
    queryClient.setQueryData(promptKeys.detail(prompt.id), prompt);
    void queryClient.invalidateQueries({ queryKey: promptKeys.all });
    void queryClient.invalidateQueries({ queryKey: reviewKeys.all });
  } });
}
