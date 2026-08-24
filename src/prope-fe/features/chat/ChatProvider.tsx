import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { AgentSurfaceContext, EMPTY_SURFACE, type AgentSurfaceState } from '@/features/chat/AgentSurfaceContext';
import { ChatContext, type ChatContextValue } from '@/features/chat/ChatContext';
import { decideChatAction, listChatConversations, readChatConversation, saveChatFeedback, streamChatMessage } from '@/features/chat/api';
import { activitiesFromTrace, mergeActivity } from '@/features/chat/activity';
import type { AttachmentFormat, ChatMessage, Conversation, UiDirective } from '@/features/chat/types';
import { isApiError } from '@/lib/apiClient';

/** How long a highlight stays lit. Long enough to notice, short enough not to nag. */
const HIGHLIGHT_MS = 4_000;

/**
 * The assistant, and the only place a directive is executed.
 *
 * **One provider for the whole `/app` shell**, because two consumers need the
 * same conversation: the chat panel in the navigation rail, and the search
 * panel's *Ask PropAI* button, which sends a turn without the panel being open.
 * Threading that through props is what the previous mocked hook did, and it is
 * why the mock could never grow a pending-action card.
 *
 * **Directives are applied here and validated on the server.** The client does
 * not re-derive them and cannot invent them: `types.uiDirectiveSchema` drops any
 * kind it does not know, and the `switch` below is total over what survives. A
 * directive that reached this function is one two independent layers agreed on.
 */
export function ChatProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [attachment, setAttachment] = useState('');
  const [attachmentFormat, setAttachmentFormat] = useState<AttachmentFormat>('txt');
  const [thinking, setThinking] = useState(false);
  const [deciding, setDeciding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [surface, setSurface] = useState<AgentSurfaceState>(EMPTY_SURFACE);
  const highlightTimer = useRef<number | undefined>(undefined);
  const interactionFrame = useRef<number | undefined>(undefined);

  useEffect(() => () => { window.clearTimeout(highlightTimer.current); window.cancelAnimationFrame(interactionFrame.current ?? 0); }, []);

  const clearHighlight = useCallback(() => setSurface((current) => ({ ...current, highlight: null })), []);
  const clearDialog = useCallback(() => setSurface((current) => ({ ...current, dialog: null })), []);
  const clearPrefill = useCallback(() => setSurface((current) => ({ ...current, prefill: null })), []);

  const apply = useCallback((directives: UiDirective[]) => {
    if (directives.some((directive) => directive.kind === 'navigate' || directive.kind === 'prefill_form' || directive.kind === 'open_dialog')) {
      setSurface((current) => ({ ...current, interacting: true }));
      window.cancelAnimationFrame(interactionFrame.current ?? 0);
      interactionFrame.current = window.requestAnimationFrame(() => {
        interactionFrame.current = window.requestAnimationFrame(() => setSurface((current) => ({ ...current, interacting: false })));
      });
    }
    for (const directive of directives) {
      switch (directive.kind) {
        case 'navigate':
          navigate(directive.arguments.to);
          break;
        case 'open_panel':
          // The rail reads its mode from the hash (`useNavigationMode`), so this
          // is a hash write rather than a second source of truth for the panel.
          if (window.location.hash !== `#${directive.arguments.panel}`) {
            window.history.pushState({ mode: directive.arguments.panel }, '', `#${directive.arguments.panel}`);
            window.dispatchEvent(new HashChangeEvent('hashchange'));
          }
          break;
        case 'select_tab':
          setSurface((current) => ({ ...current, tab: directive.arguments.tab }));
          break;
        case 'set_step':
          setSurface((current) => ({ ...current, step: directive.arguments.step }));
          break;
        case 'open_dialog':
          setSurface((current) => ({ ...current, dialog: directive.arguments.dialog }));
          break;
        case 'prefill_form':
          setSurface((current) => ({ ...current, prefill: { form: directive.arguments.form, fields: directive.arguments.fields } }));
          break;
        case 'highlight':
          setSurface((current) => ({ ...current, highlight: directive.arguments.target }));
          window.clearTimeout(highlightTimer.current);
          highlightTimer.current = window.setTimeout(clearHighlight, HIGHLIGHT_MS);
          break;
      }
    }
  }, [clearHighlight, navigate]);

  const refreshConversations = useCallback(() => {
    void listChatConversations().then(setConversations).catch(() => setConversations([]));
  }, []);

  useEffect(refreshConversations, [refreshConversations]);

  const send = useCallback((providedText?: string) => {
    const text = (providedText ?? input).trim();
    if (!text || thinking) return;

    const carried = attachment.trim();
    const localId = `local-${Date.now()}`;
    const streamId = `stream-${Date.now()}`;
    setMessages((current) => [
      ...current,
      { id: localId, role: 'user', text },
      { id: streamId, role: 'agent', text: '', activities: [], streaming: true },
    ]);
    setInput('');
    setAttachment('');
    setError(null);
    setThinking(true);

    void streamChatMessage(
      { conversationId, text, attachment: carried || null, attachmentFormat },
      {
        onActivity: (activity) => setMessages((current) => current.map((message) => (
          message.id === streamId
            ? { ...message, activities: mergeActivity(message.activities ?? [], activity) }
            : message
        ))),
      },
    )
      .then((turn) => {
        setConversationId(turn.conversation_id);
        setMessages((current) => current.map((message) => message.id === streamId ? {
          ...message,
          id: turn.message_id,
          text: turn.reply,
          code: turn.code,
          citations: turn.citations,
          trace: turn.trace,
          degraded: turn.degraded,
          pending: turn.pending,
          activities: message.activities?.length ? message.activities : activitiesFromTrace(turn.trace),
          streaming: false,
        } : message));
        apply(turn.directives);
        refreshConversations();
      })
      .catch((cause) => {
        setMessages((current) => current.map((message) => message.id === streamId
          ? { ...message, streaming: false, code: 'chat_agent_unavailable' }
          : message));
        setError(isApiError(cause) ? cause.code : 'chat_agent_unavailable');
      })
      .finally(() => setThinking(false));
  }, [apply, attachment, attachmentFormat, conversationId, input, refreshConversations, thinking]);

  const decide = useCallback((actionId: string, approve: boolean, edits?: Record<string, string>) => {
    if (deciding) return;
    setDeciding(true);
    setError(null);

    void decideChatAction(actionId, approve, edits)
      .then((decision) => {
        // The card stops offering buttons rather than disappearing: what was
        // decided, and what it produced, is the audit trail the person came for.
        setMessages((current) => current.map((message) => (
          message.pending?.id === actionId
            ? {
                ...message,
                settled: decision.status === 'confirmed' ? 'confirmed' : 'rejected',
                actionResult: { promptId: decision.prompt_id, versionId: decision.version_id },
              }
            : message
        )));
        apply(decision.directives);

        // The server runs one automatic turn after the settle — the agent
        // picking the remaining task back up (an eval run proposed on a freshly
        // approved revision) or acknowledging the rejection. It arrives here as
        // a stored turn and renders like any other agent message, card included:
        // that new pending is the next human gate, not this decision's echo.
        const followUp = decision.continuation;
        if (followUp && (followUp.reply || followUp.code || followUp.pending)) {
          setMessages((current) => [
            ...current,
            {
              id: followUp.message_id,
              role: 'agent',
              text: followUp.reply,
              code: followUp.code,
              citations: followUp.citations,
              trace: followUp.trace,
              degraded: followUp.degraded,
              pending: followUp.pending,
              activities: activitiesFromTrace(followUp.trace),
            },
          ]);
          apply(followUp.directives);
        }
      })
      .catch((cause) => setError(isApiError(cause) ? cause.code : 'chat_agent_unavailable'))
      .finally(() => setDeciding(false));
  }, [apply, deciding]);

  const openConversation = useCallback((id: string) => {
    void readChatConversation(id).then((transcript) => {
      setConversationId(transcript.conversation.id);
      setMessages(transcript.messages.map((message) => ({
        id: message.id,
        role: message.role,
        text: message.text,
        citations: message.citations,
        trace: message.trace,
        activities: activitiesFromTrace(message.trace),
        // Only the LAST agent turn can still hold the open proposal, and the
        // server says which one it is — reconstructing it from the transcript
        // would offer a stale card on every earlier turn that once had one.
        pending: transcript.pending && message.id === transcript.messages.at(-1)?.id ? transcript.pending : null,
      })));
      setError(null);
    }).catch((cause) => setError(isApiError(cause) ? cause.code : 'chat_agent_unavailable'));
  }, []);

  const startNewConversation = useCallback(() => {
    setConversationId(null);
    setMessages([]);
    setAttachment('');
    setError(null);
  }, []);

  const retry = useCallback((messageId: string) => {
    const index = messages.findIndex((message) => message.id === messageId);
    const previous = messages.slice(0, index).reverse().find((message) => message.role === 'user');
    if (previous) send(previous.text);
  }, [messages, send]);

  const feedback = useCallback((messageId: string, rating: 'helpful' | 'not_helpful', reason?: 'incorrect' | 'unsupported_source' | 'misunderstood' | 'other') => {
    void saveChatFeedback(messageId, rating, reason).then(() => {
      setMessages((current) => current.map((message) => message.id === messageId ? { ...message, feedback: rating } : message));
    }).catch((cause) => setError(isApiError(cause) ? cause.code : 'chat_agent_unavailable'));
  }, []);

  const chat = useMemo<ChatContextValue>(() => ({
    conversationId,
    conversations,
    messages,
    input,
    setInput,
    attachment,
    setAttachment,
    attachmentFormat,
    setAttachmentFormat,
    thinking,
    deciding,
    error,
    send,
    retry,
    feedback,
    decide,
    openConversation,
    startNewConversation,
  }), [attachment, attachmentFormat, conversationId, conversations, decide, deciding, error, feedback, input, messages, openConversation, retry, send, startNewConversation, thinking]);

  const agentSurface = useMemo(() => ({ ...surface, apply, clearDialog, clearPrefill, clearHighlight }), [apply, clearDialog, clearHighlight, clearPrefill, surface]);

  return (
    <ChatContext.Provider value={chat}>
      <AgentSurfaceContext.Provider value={agentSurface}>{children}</AgentSurfaceContext.Provider>
    </ChatContext.Provider>
  );
}
