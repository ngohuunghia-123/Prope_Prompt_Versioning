import { randomUUID } from 'node:crypto';
import { z } from 'zod';
import { sessionBindingSchema, sessionChatRequestSchema, type SessionBinding, type SessionSnapshot } from '@connector/sessionChatContracts';
import { actionDecisionSchema, transcriptSchema, turnSchema } from '@/features/chat/types';
import { ConnectorError, ManagementApi } from './api';
import { Broker } from './broker';
import type { readCodexSession } from './codexSession';
import { selectSessionContext } from './sessionContext';

const writableTools = new Set(['create_prompt', 'create_revision', 'start_eval_run']);
const promptPreviewSchema = z.object({ canonical_xml: z.string().min(1).max(32768), original_source: z.string().max(32768) });
type SourceReader = (threadId: string) => ReturnType<typeof readCodexSession>;
type SessionSource = SessionSnapshot & { messages: Awaited<ReturnType<SourceReader>>['messages'] };
type Consent = (operation: 'grant' | 'send' | 'decide', threadId: string, binding?: SessionBinding) => Promise<boolean>;

export class SessionChat {
  private snapshot: SessionSource | null = null;
  private lastQuestion = '';
  private conversationId: string | null = null;
  private readonly pending = new Map<string, string>();
  private readonly messageIds = new Set<string>();
  private generation = 0;
  private busy = false;
  constructor(private readonly api: ManagementApi, private readonly broker: Broker,
    private readonly read: SourceReader, private readonly consent: Consent,
    private readonly chooseBinding: () => Promise<SessionBinding | null> = async () => null) {}
  clear() { this.generation += 1; this.snapshot = null; this.lastQuestion = ''; this.conversationId = null; this.pending.clear(); this.messageIds.clear(); }
  private view(snapshot: SessionSource): SessionSnapshot {
    return { grant_id: snapshot.grant_id, snapshot_id: snapshot.snapshot_id, connection_id: snapshot.connection_id,
      thread_id: snapshot.thread_id, title: snapshot.title, host: snapshot.host, read_at: snapshot.read_at,
      has_content: snapshot.has_content, uncertain: snapshot.uncertain };
  }
  private async current(id?: string) {
    const snapshot = this.snapshot;
    if (!snapshot || (id && snapshot.grant_id !== id)) throw new ConnectorError('session_grant_required', 403);
    try {
      await this.broker.withCodexConversation(snapshot.connection_id, snapshot.thread_id, async () => null);
    } catch (error) { if (this.snapshot === snapshot) this.clear(); throw error; }
    if (this.snapshot !== snapshot) throw new ConnectorError('session_changed', 409);
    return snapshot;
  }
  private context(snapshot: SessionSource, question: string, previousQuestion: string) {
    const transcript = selectSessionContext(snapshot.messages, question, previousQuestion);
    return { host: snapshot.host, thread_id: snapshot.thread_id, snapshot_id: snapshot.snapshot_id, transcript };
  }
  private async refresh(snapshot: SessionSource) {
    const source = await this.broker.withCodexConversation(snapshot.connection_id, snapshot.thread_id, this.read);
    if (this.snapshot !== snapshot) throw new ConnectorError('session_changed', 409);
    const next: SessionSource = { ...snapshot, ...source, snapshot_id: randomUUID(), read_at: Date.now(), has_content: source.messages.length > 0 };
    this.snapshot = next; return this.view(next);
  }
  private verifyPending(pending: z.infer<typeof turnSchema>['pending']) {
    if (pending && ['create_prompt', 'create_revision'].includes(pending.tool)) promptPreviewSchema.parse(pending.preview);
    if (pending?.tool === 'create_prompt' && !this.snapshot?.messages.some((message) => message.text === pending.preview.original_source
      && (!pending.preview.session_message_id || message.id === pending.preview.session_message_id))) throw new ConnectorError('session_prompt_not_selected', 403);
  }
  private remember(raw: unknown) {
    const turn = turnSchema.parse(raw); this.verifyPending(turn.pending);
    this.conversationId = turn.conversation_id; this.messageIds.add(turn.message_id);
    if (turn.pending) this.pending.set(turn.pending.id, turn.pending.tool);
    // Extension navigation is explicit. Web-only directives never execute here.
    return { ...turn, directives: [] };
  }
  async execute(raw: unknown): Promise<unknown> {
    const input = sessionChatRequestSchema.parse(raw);
    const deadline = 'expires_at' in input ? Math.min(input.expires_at, Date.now() + 175_000) : Infinity;
    if (Date.now() >= deadline) throw new ConnectorError('session_request_expired', 409);
    if (input.operation === 'state') {
      if (!this.snapshot) return null;
      try { return this.view(await this.current()); } catch { return null; }
    }
    if (input.operation === 'revoke') {
      if (this.snapshot?.grant_id !== input.grant_id) throw new ConnectorError('session_grant_required', 403);
      this.clear(); return null;
    }
    if (this.busy) throw new ConnectorError('operation_in_progress', 409);
    this.busy = true;
    const generation = this.generation;
    try {
      if (input.operation === 'grant') {
        await this.broker.withCodexConversation(input.connection_id, input.thread_id, async () => null);
        if (!await this.consent('grant', input.thread_id)) throw new ConnectorError('cancelled');
        if (generation !== this.generation) throw new ConnectorError('session_changed', 409);
        await this.broker.withCodexConversation(input.connection_id, input.thread_id, async () => null);
        if (generation !== this.generation) throw new ConnectorError('session_changed', 409);
        this.clear();
        const snapshot: SessionSource = { grant_id: randomUUID(), snapshot_id: randomUUID(), connection_id: input.connection_id,
          thread_id: input.thread_id, host: 'codex', title: null, messages: [], read_at: Date.now(), has_content: false, uncertain: false };
        this.snapshot = snapshot;
        try { return await this.refresh(snapshot); } catch (error) { if (this.snapshot === snapshot) this.clear(); throw error; }
      }
      const snapshot = await this.current(input.grant_id);
      if (input.operation === 'refresh') return await this.refresh(snapshot);
      if (input.operation === 'history') {
        if (!this.conversationId) return null;
        const result = transcriptSchema.parse(await this.api.request(`/api/v1/chat/conversations/${encodeURIComponent(this.conversationId)}`));
        await this.current(input.grant_id);
        if (this.snapshot !== snapshot || result.conversation.id !== this.conversationId) throw new ConnectorError('session_changed', 409);
        for (const message of result.messages) if (message.role === 'agent') this.messageIds.add(message.id);
        if (result.pending) {
          this.verifyPending(result.pending);
          this.pending.set(result.pending.id, result.pending.tool);
        }
        return result;
      }
      if (snapshot.uncertain) throw new ConnectorError('session_outcome_unknown', 409);
      if (input.operation === 'feedback') {
        if (!this.messageIds.has(input.message_id)) throw new ConnectorError('scope_denied', 403);
        return await this.api.request(`/api/v1/chat/messages/${encodeURIComponent(input.message_id)}/feedback`, 'POST', { rating: input.rating, reason: input.reason ?? null });
      }
      const previousQuestion = input.operation === 'send' && !input.conversation_id ? '' : this.lastQuestion;
      const context = this.context(snapshot, input.operation === 'send' ? input.text : this.lastQuestion, previousQuestion);
      if (input.operation === 'send') {
        if (snapshot.snapshot_id !== input.snapshot_id) throw new ConnectorError('session_snapshot_changed', 409);
        if (input.conversation_id && input.conversation_id !== this.conversationId) throw new ConnectorError('scope_denied', 403);
        if (input.attachment && !snapshot.messages.some((message) => message.text === input.attachment)) throw new ConnectorError('session_prompt_not_selected', 403);
      } else if (!this.pending.has(input.action_id) || (input.approve && !writableTools.has(this.pending.get(input.action_id) ?? ''))) throw new ConnectorError('session_action_denied', 403);
      let binding: SessionBinding | undefined;
      if (input.operation === 'decide' && input.approve && ['create_prompt', 'create_revision'].includes(this.pending.get(input.action_id) ?? '')) {
        const selected = await this.chooseBinding();
        if (!selected) throw new ConnectorError('cancelled');
        binding = sessionBindingSchema.parse(selected);
      }
      if (Date.now() >= deadline) throw new ConnectorError('session_request_expired', 409);
      if (await this.current(input.grant_id) !== snapshot) throw new ConnectorError('session_snapshot_changed', 409);
      if ((input.operation === 'send' || input.approve) && !await this.consent(input.operation, snapshot.thread_id, binding)) throw new ConnectorError('cancelled');
      if (Date.now() >= deadline) throw new ConnectorError('session_request_expired', 409);
      if (await this.current(input.grant_id) !== snapshot) throw new ConnectorError('session_snapshot_changed', 409);
      if (Date.now() >= deadline) throw new ConnectorError('session_request_expired', 409);
      try {
        if (input.operation === 'send') {
          if (!input.conversation_id) { this.conversationId = null; this.pending.clear(); this.messageIds.clear(); }
          const result = await this.api.request('/api/v1/chat/messages', 'POST', {
            conversation_id: this.conversationId, text: input.text, attachment: input.attachment,
            attachment_format: input.attachment_format, session_context: context,
          }, 150_000);
          await this.current(input.grant_id);
          if (this.snapshot !== snapshot) throw new ConnectorError('session_snapshot_changed', 409);
          const turn = this.remember(result); this.lastQuestion = input.text;
          return turn;
        }
        const result = actionDecisionSchema.parse(await this.api.request(`/api/v1/chat/actions/${encodeURIComponent(input.action_id)}`, 'POST', {
          approve: input.approve, edits: input.edits, session_context: context, ...(binding ? { provider_binding: binding } : {}),
        }, 150_000));
        await this.current(input.grant_id);
        if (this.snapshot !== snapshot) throw new ConnectorError('session_snapshot_changed', 409);
        this.pending.delete(input.action_id);
        return { ...result, directives: [], secret_once: null, continuation: null };
      } catch (error) {
        if (this.snapshot === snapshot) snapshot.uncertain = true;
        throw error;
      }
    } finally { this.busy = false; }
  }
}
