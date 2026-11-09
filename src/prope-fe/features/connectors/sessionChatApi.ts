import { ApiError } from '@/lib/apiClient';
import { callHost } from '@/features/connectors/bridge';
import { sessionSnapshotSchema, type SessionSnapshot } from '@/features/connectors/sessionChatContracts';
import { actionDecisionSchema, feedbackSchema, transcriptSchema, turnSchema } from '@/features/chat/types';
import type { ChatTransport } from '@/features/chat/api';

const uncertainGrants = new Set<string>();
export const getSessionChat = async () => {
  const snapshot = sessionSnapshotSchema.nullable().parse(await callHost('session_chat', { operation: 'state' }));
  if (!snapshot) { uncertainGrants.clear(); return null; }
  return { ...snapshot, uncertain: snapshot.uncertain || uncertainGrants.has(snapshot.grant_id) };
};
export const grantSessionChat = async (connectionId: string, threadId: string) => {
  const snapshot = sessionSnapshotSchema.parse(await callHost('session_chat', { operation: 'grant', connection_id: connectionId, thread_id: threadId }));
  uncertainGrants.clear(); return snapshot;
};
export const refreshSessionChat = async (grantId: string) => {
  const snapshot = sessionSnapshotSchema.parse(await callHost('session_chat', { operation: 'refresh', grant_id: grantId }));
  return { ...snapshot, uncertain: snapshot.uncertain || uncertainGrants.has(snapshot.grant_id) };
};
export const revokeSessionChat = (grantId: string) => callHost('session_chat', { operation: 'revoke', grant_id: grantId });

export function sessionChatTransport(snapshot: SessionSnapshot, changed: () => Promise<unknown>): ChatTransport {
  const execute = async (operation: string, payload: object) => {
    const mutates = ['send', 'decide', 'feedback'].includes(operation);
    if (mutates && uncertainGrants.has(snapshot.grant_id)) throw new ApiError(409, 'session_outcome_unknown', 'session_outcome_unknown');
    try { return await callHost('session_chat', { operation, grant_id: snapshot.grant_id, ...(['send', 'decide'].includes(operation) ? { expires_at: Date.now() + 175_000 } : {}), ...payload }); }
    catch (error) { if (mutates && error instanceof ApiError && error.code === 'outcome_unknown') uncertainGrants.add(snapshot.grant_id); throw error; }
    finally { await changed(); }
  };
  const history = async () => transcriptSchema.nullable().parse(await execute('history', {}));
  return {
    send: async (input) => {
      if (!input.text.trim()) throw new ApiError(422, 'session_question_required', 'session_question_required');
      return turnSchema.parse(await execute('send', { snapshot_id: snapshot.snapshot_id, conversation_id: input.conversationId ?? null,
        text: input.text, attachment: input.attachment ?? null, attachment_format: input.attachmentFormat ?? 'txt' }));
    },
    decide: async (actionId, approve, edits) => actionDecisionSchema.parse(await execute('decide', { action_id: actionId, approve, ...(edits ? { edits } : {}) })),
    feedback: async (messageId, rating, reason) => feedbackSchema.parse(await execute('feedback', { message_id: messageId, rating, ...(reason ? { reason } : {}) })),
    list: async () => { const transcript = await history(); return transcript ? [transcript.conversation] : []; },
    read: async (id) => { const transcript = await history(); if (!transcript || transcript.conversation.id !== id) throw new ApiError(403, 'scope_denied', 'scope_denied'); return transcript; },
  };
}
