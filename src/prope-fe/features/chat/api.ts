import { apiRequest } from '@/lib/apiClient';
import {
  actionDecisionSchema,
  conversationListSchema,
  pipelineSchema,
  transcriptSchema,
  turnSchema,
  type ActionDecision,
  type AttachmentFormat,
  type Conversation,
  type Pipeline,
  type Transcript,
  type Turn,
} from '@/features/chat/types';

/**
 * The five chat routes.
 *
 * `decideChatAction` is separate from `sendChatMessage` on purpose and the
 * separation is the product's approval gate, not a REST preference: the agent
 * proposes a write, the person reads the card, and *this* request is the
 * approval. A `confirm` flag on the send would put the approval and the thing
 * approved in the same breath, which is the rubber stamp the design exists to
 * avoid.
 */

export function sendChatMessage(input: {
  conversationId?: string | null;
  text: string;
  attachment?: string | null;
  attachmentFormat?: AttachmentFormat;
}): Promise<Turn> {
  return apiRequest('/api/v1/chat/messages', {
    method: 'POST',
    schema: turnSchema,
    body: JSON.stringify({
      conversation_id: input.conversationId ?? null,
      text: input.text,
      attachment: input.attachment ?? null,
      attachment_format: input.attachmentFormat ?? 'txt',
    }),
  });
}

export function decideChatAction(actionId: string, approve: boolean): Promise<ActionDecision> {
  return apiRequest(`/api/v1/chat/actions/${encodeURIComponent(actionId)}`, {
    method: 'POST',
    schema: actionDecisionSchema,
    body: JSON.stringify({ approve }),
  });
}

export async function listChatConversations(): Promise<Conversation[]> {
  const payload = await apiRequest('/api/v1/chat/conversations', { schema: conversationListSchema });
  return payload.conversations;
}

export function readChatConversation(conversationId: string): Promise<Transcript> {
  return apiRequest(`/api/v1/chat/conversations/${encodeURIComponent(conversationId)}`, {
    schema: transcriptSchema,
  });
}

/**
 * The pipeline's shape. Reads no row and is identical for every actor, which is
 * why the caller may cache it for the whole session and never revalidate it.
 */
export function readChatPipeline(): Promise<Pipeline> {
  return apiRequest('/api/v1/chat/pipeline', { schema: pipelineSchema });
}
