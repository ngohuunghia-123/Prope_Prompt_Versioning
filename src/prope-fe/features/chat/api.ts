import { apiRequest } from '@/lib/apiClient';
import {
  actionDecisionSchema,
  chatActivitySchema,
  conversationListSchema,
  pipelineSchema,
  feedbackSchema,
  transcriptSchema,
  turnSchema,
  type ActionDecision,
  type AttachmentFormat,
  type ChatActivity,
  type Conversation,
  type Pipeline,
  type Feedback,
  type Transcript,
  type Turn,
} from '@/features/chat/types';

class ChatStreamError extends Error {
  constructor(public readonly receivedEvent: boolean) {
    super('chat stream ended before a completed turn');
  }
}

export interface ChatStreamHandlers {
  onActivity: (activity: ChatActivity) => void;
}

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

export async function streamChatMessage(
  input: Parameters<typeof sendChatMessage>[0],
  handlers: ChatStreamHandlers,
): Promise<Turn> {
  let receivedEvent = false;
  try {
    const response = await fetch('/api/v1/chat/messages/stream', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({
        conversation_id: input.conversationId ?? null,
        text: input.text,
        attachment: input.attachment ?? null,
        attachment_format: input.attachmentFormat ?? 'txt',
      }),
    });
    if (!response.ok || !response.body) throw new ChatStreamError(false);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let completed: Turn | undefined;

    const consume = (block: string) => {
      const lines = block.split('\n');
      const event = lines.find((line) => line.startsWith('event:'))?.slice(6).trim();
      const data = lines.filter((line) => line.startsWith('data:')).map((line) => line.slice(5).trim()).join('\n');
      if (!event || !data) return;
      receivedEvent = true;
      const payload: unknown = JSON.parse(data);
      if (event.startsWith('activity.')) handlers.onActivity(chatActivitySchema.parse(payload));
      if (event === 'turn.completed') completed = turnSchema.parse(payload);
      if (event === 'turn.failed') throw new ChatStreamError(true);
    };

    while (true) {
      const chunk = await reader.read();
      buffer += decoder.decode(chunk.value, { stream: !chunk.done }).replaceAll('\r\n', '\n');
      let boundary = buffer.indexOf('\n\n');
      while (boundary >= 0) {
        consume(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf('\n\n');
      }
      if (chunk.done) break;
    }
    if (!completed) throw new ChatStreamError(receivedEvent);
    return completed;
  } catch (cause) {
    if (cause instanceof ChatStreamError && !cause.receivedEvent) return sendChatMessage(input);
    throw cause;
  }
}

export function decideChatAction(actionId: string, approve: boolean): Promise<ActionDecision> {
  return apiRequest(`/api/v1/chat/actions/${encodeURIComponent(actionId)}`, {
    method: 'POST',
    schema: actionDecisionSchema,
    body: JSON.stringify({ approve }),
  });
}

export function saveChatFeedback(
  messageId: string,
  rating: 'helpful' | 'not_helpful',
  reason?: 'incorrect' | 'unsupported_source' | 'misunderstood' | 'other',
): Promise<Feedback> {
  return apiRequest(`/api/v1/chat/messages/${encodeURIComponent(messageId)}/feedback`, {
    method: 'POST',
    schema: feedbackSchema,
    body: JSON.stringify({ rating, reason: reason ?? null }),
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
