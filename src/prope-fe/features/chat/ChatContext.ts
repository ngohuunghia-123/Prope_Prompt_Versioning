import { createContext, useContext } from 'react';
import type { AttachmentFormat, ChatMessage, Conversation } from '@/features/chat/types';

export interface ChatContextValue {
  conversationId: string | null;
  conversations: Conversation[];
  messages: ChatMessage[];
  input: string;
  setInput: (value: string) => void;
  /** A whole prompt the person is asking about. Separate from `input` so the
   *  guardrail layer inspects a question rather than a 4 KB prompt. */
  attachment: string;
  setAttachment: (value: string) => void;
  attachmentFormat: AttachmentFormat;
  setAttachmentFormat: (value: AttachmentFormat) => void;
  thinking: boolean;
  deciding: boolean;
  /** A machine code the client translates (ADR-0053), never a server string. */
  error: string | null;
  send: (text?: string) => void;
  retry: (messageId: string) => void;
  feedback: (messageId: string, rating: 'helpful' | 'not_helpful', reason?: 'incorrect' | 'unsupported_source' | 'misunderstood' | 'other') => void;
  decide: (actionId: string, approve: boolean) => void;
  openConversation: (id: string) => void;
  startNewConversation: () => void;
}

export const ChatContext = createContext<ChatContextValue | null>(null);

/**
 * The conversation, for the panel and for *Ask PropAI*.
 *
 * Throws outside the provider rather than returning a stub, unlike
 * `useAgentSurface`. The asymmetry is deliberate: a page reading agent state
 * outside the provider should render as if the assistant did not exist, and a
 * component trying to *send a message* outside it is a wiring mistake that
 * should be loud.
 */
export function useChat(): ChatContextValue {
  const value = useContext(ChatContext);
  if (!value) throw new Error('useChat must be used inside <ChatProvider>');
  return value;
}
