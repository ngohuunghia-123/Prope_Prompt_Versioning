import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { applyMockRevision, promptKeys, readMockPromptsSnapshot } from '@/features/preservation/queries';
import type { PreservedPrompt } from '@/features/preservation/types';
import {
  revisionFormSchema,
  revisionWorkspaceSchema,
  type PromptRevision,
  type RevisionFormValues,
  type RevisionWorkspace,
} from '@/features/revisions/types';

const wait = () => new Promise((resolve) => window.setTimeout(resolve, 280));
const workspaces = new Map<string, RevisionWorkspace>();
function createWorkspace(promptId: string) {
  const prompt = readMockPromptsSnapshot().find((item) => item.id === promptId);
  if (!prompt) return revisionWorkspaceSchema.parse({ permission: promptId === 'access-unavailable' ? 'denied' : 'edit', revisions: [] });
  const revisions = Array.from({ length: prompt.currentRevision }, (_, index) => {
    const number = prompt.currentRevision - index;
    const isCurrent = number === prompt.currentRevision;
    const status = isCurrent ? prompt.status : number === prompt.trustedRevision || number === prompt.releasedRevision ? 'approved' as const : 'draft' as const;
    return {
      id: number === prompt.currentRevision ? prompt.currentVersionId : `${promptId}-revision-${number}`,
      promptId, number, content: isCurrent ? prompt.content : `${prompt.content}\n\n[Revision ${number}]`,
      providerName: prompt.providerName, upstreamModel: prompt.upstreamModel, temperature: prompt.temperature,
      maxTokens: prompt.maxTokens, fallbackAnswer: prompt.fallbackAnswer,
      summary: isCurrent ? 'Revision hiện hành' : `Revision ${number} được lưu trong lịch sử`,
      editorName: prompt.ownerName, createdAt: new Date(new Date(prompt.createdAt).getTime() + number * 86_400_000).toISOString(),
      isCurrent, status,
    };
  });
  return revisionWorkspaceSchema.parse({
    permission: promptId === 'access-unavailable' ? 'denied' : 'edit',
    revisions,
  });
}

async function readWorkspace(promptId: string) {
  await wait();
  if (!promptId) throw new Error('PROMPT_NOT_FOUND');
  const workspace = workspaces.get(promptId) ?? createWorkspace(promptId);
  workspaces.set(promptId, workspace);
  return revisionWorkspaceSchema.parse(workspace);
}

async function saveRevision(input: RevisionFormValues & { promptId: string }) {
  await wait();
  const values = revisionFormSchema.parse(input);
  if (values.content.includes('[save-fail]')) throw new Error('REVISION_SAVE_FAILED');
  const workspace = workspaces.get(input.promptId) ?? createWorkspace(input.promptId);
  if (workspace.permission === 'denied') throw new Error('REVISION_PERMISSION_DENIED');
  const nextNumber = Math.max(0, ...workspace.revisions.map((revision) => revision.number)) + 1;
  const createdAt = new Date().toISOString();
  const revision: PromptRevision = {
    id: `${input.promptId}-revision-${nextNumber}`,
    promptId: input.promptId,
    number: nextNumber,
    content: values.content,
    providerName: values.providerName,
    upstreamModel: values.upstreamModel,
    temperature: values.temperature,
    maxTokens: values.maxTokens,
    fallbackAnswer: values.fallbackAnswer,
    summary: values.summary,
    editorName: 'Linh Nguyễn',
    createdAt,
    isCurrent: true,
    status: 'draft',
  };
  const updated = revisionWorkspaceSchema.parse({ ...workspace, revisions: [revision, ...workspace.revisions.map((item) => ({ ...item, isCurrent: false }))] });
  workspaces.set(input.promptId, updated);
  const prompt = applyMockRevision(input.promptId, { ...revision, versionId: revision.id }, revision.createdAt);
  return { revision, workspace: updated, prompt };
}

export const revisionKeys = { detail: (promptId: string) => ['prompt-revisions', promptId] as const };
export const revisionOptions = (promptId: string) => queryOptions({ queryKey: revisionKeys.detail(promptId), queryFn: () => readWorkspace(promptId) });

export function useSaveRevision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: saveRevision,
    onSuccess: ({ revision, workspace, prompt }) => {
      queryClient.setQueryData(revisionKeys.detail(revision.promptId), workspace);
      queryClient.setQueryData<PreservedPrompt>(promptKeys.detail(revision.promptId), prompt);
      void queryClient.invalidateQueries({ queryKey: promptKeys.all });
    },
  });
}
