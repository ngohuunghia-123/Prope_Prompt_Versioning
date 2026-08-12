import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { applyMockAccess, promptKeys, readMockPromptsSnapshot } from '@/features/preservation/queries';
import type { PreservedPrompt } from '@/features/preservation/types';
import {
  accessFormSchema,
  accessRecordSchema,
  transferFormSchema,
  grantFormSchema,
  type AccessFormValues,
  type AccessRecord,
  type TransferFormValues,
  type GrantFormValues,
} from '@/features/access-management/types';

const wait = () => new Promise((resolve) => window.setTimeout(resolve, 280));
const owners = [
  { id: 'linh', name: 'Linh Nguyễn', role: 'owner' },
  { id: 'an', name: 'An Trần', role: 'product' },
  { id: 'mai', name: 'Mai Lê', role: 'engineer' },
];
const records = new Map<string, AccessRecord>();

function createRecord(promptId: string) {
  const prompt = readMockPromptsSnapshot().find((item) => item.id === promptId);
  return accessRecordSchema.parse({
    promptId,
    permission: promptId === 'access-unavailable' ? 'denied' : 'manage',
    access: prompt?.access ?? 'private',
    ownerId: prompt?.ownerId ?? 'linh',
    ownerName: prompt?.ownerName ?? 'Linh Nguyễn',
    availableOwners: owners,
    grants: [{ id: `${promptId}-grant-mai`, userId: 'mai', userName: 'Mai Lê', level: 'editor' }],
    activity: [{ id: `${promptId}-activity-initial`, kind: 'granted', actorName: 'Linh Nguyễn', subjectName: 'Mai Lê', value: 'editor', occurredAt: '2026-08-10T08:30:00.000Z' }],
    lastActivityAt: '2026-08-10T08:30:00.000Z',
  });
}

async function grantAccess(input: GrantFormValues & { promptId: string }) {
  await wait();
  const values = grantFormSchema.parse(input);
  const current = records.get(input.promptId) ?? createRecord(input.promptId);
  const candidate = current.availableOwners.find((owner) => owner.id === values.userId);
  if (!candidate || candidate.id === current.ownerId) throw new Error('GRANTEE_NOT_FOUND');
  const grant = { id: `${input.promptId}-grant-${candidate.id}`, userId: candidate.id, userName: candidate.name, level: values.level };
  const grants = [...current.grants.filter((item) => item.userId !== candidate.id), grant];
  const occurredAt = new Date().toISOString();
  const activity = [{ id: `${input.promptId}-activity-${Date.now()}`, kind: 'granted' as const, actorName: 'Linh Nguyễn', subjectName: candidate.name, value: values.level, occurredAt }, ...current.activity];
  const updated = accessRecordSchema.parse({ ...current, grants, activity, lastActivityAt: occurredAt });
  records.set(input.promptId, updated);
  return updated;
}

async function revokeAccess(input: { promptId: string; grantId: string }) {
  await wait();
  const current = records.get(input.promptId) ?? createRecord(input.promptId);
  const revoked = current.grants.find((grant) => grant.id === input.grantId);
  if (!revoked) throw new Error('GRANT_NOT_FOUND');
  const occurredAt = new Date().toISOString();
  const activity = [{ id: `${input.promptId}-activity-${Date.now()}`, kind: 'revoked' as const, actorName: 'Linh Nguyễn', subjectName: revoked.userName, value: revoked.level, occurredAt }, ...current.activity];
  const updated = accessRecordSchema.parse({ ...current, grants: current.grants.filter((grant) => grant.id !== input.grantId), activity, lastActivityAt: occurredAt });
  records.set(input.promptId, updated);
  return updated;
}

async function readAccess(promptId: string) {
  await wait();
  if (!promptId) throw new Error('PROMPT_NOT_FOUND');
  if (promptId === 'empty-access') return null;
  const record = records.get(promptId) ?? createRecord(promptId);
  records.set(promptId, record);
  return accessRecordSchema.parse(record);
}

async function updateAccess(input: AccessFormValues & { promptId: string }) {
  await wait();
  const values = accessFormSchema.parse(input);
  const current = records.get(input.promptId) ?? createRecord(input.promptId);
  const occurredAt = new Date().toISOString();
  const activity = [{ id: `${input.promptId}-activity-${Date.now()}`, kind: 'accessChanged' as const, actorName: 'Linh Nguyễn', subjectName: null, value: values.access, occurredAt }, ...current.activity];
  const updated = accessRecordSchema.parse({ ...current, access: values.access, activity, lastActivityAt: occurredAt });
  records.set(input.promptId, updated);
  return updated;
}

async function transferOwnership(input: TransferFormValues & { promptId: string }) {
  await wait();
  const values = transferFormSchema.parse(input);
  const current = records.get(input.promptId) ?? createRecord(input.promptId);
  const owner = current.availableOwners.find((candidate) => candidate.id === values.newOwnerId);
  if (!owner) throw new Error('OWNER_NOT_FOUND');
  const occurredAt = new Date().toISOString();
  const activity = [{ id: `${input.promptId}-activity-${Date.now()}`, kind: 'ownershipTransferred' as const, actorName: current.ownerName, subjectName: owner.name, value: null, occurredAt }, ...current.activity];
  const updated = accessRecordSchema.parse({ ...current, ownerId: owner.id, ownerName: owner.name, activity, lastActivityAt: occurredAt });
  records.set(input.promptId, updated);
  return updated;
}

export const accessKeys = { detail: (promptId: string) => ['prompt-access', promptId] as const };
export const accessOptions = (promptId: string) => queryOptions({ queryKey: accessKeys.detail(promptId), queryFn: () => readAccess(promptId) });

function syncPrompt(queryClient: ReturnType<typeof useQueryClient>, record: AccessRecord) {
  const prompt = applyMockAccess(record.promptId, { access: record.access, ownerId: record.ownerId, ownerName: record.ownerName }, record.lastActivityAt);
  queryClient.setQueryData<PreservedPrompt>(promptKeys.detail(record.promptId), prompt);
  void queryClient.invalidateQueries({ queryKey: promptKeys.all });
  void queryClient.invalidateQueries({ queryKey: ['trusted-registry'] });
}

export function useUpdateAccess() {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: updateAccess, onSuccess: (record) => { queryClient.setQueryData(accessKeys.detail(record.promptId), record); syncPrompt(queryClient, record); } });
}

export function useTransferOwnership() {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: transferOwnership, onSuccess: (record) => { queryClient.setQueryData(accessKeys.detail(record.promptId), record); syncPrompt(queryClient, record); } });
}

export function useGrantAccess() {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: grantAccess, onSuccess: (record) => { queryClient.setQueryData(accessKeys.detail(record.promptId), record); syncPrompt(queryClient, record); } });
}

export function useRevokeAccess() {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: revokeAccess, onSuccess: (record) => { queryClient.setQueryData(accessKeys.detail(record.promptId), record); syncPrompt(queryClient, record); } });
}
