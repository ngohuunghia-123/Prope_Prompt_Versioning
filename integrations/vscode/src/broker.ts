import { randomBytes, randomUUID, timingSafeEqual } from 'node:crypto';
import { createServer, type IncomingMessage } from 'node:http';
import { z } from 'zod';
import { captureSchema, conversationIdSchema, evaluationProposalSchema, revisionProposalSchema, type ConversationObservation, type ConversationTitle } from '@connector/contracts';
import { ConnectorError, ManagementApi, promptSchema } from './api';
import { Proposals } from './proposals';

interface Pair { code: string; ticket: string; expires: number; client?: { name: string; version: string }; conversations?: Map<string, ConversationObservation>; conversationHistoryLimited?: boolean; lease?: number; heartbeat?: number; token?: string; namespace?: string; workspace?: string; actor?: string; }
const pairStartSchema = z.object({ client: z.object({ name: z.string().trim().min(1).max(100), version: z.string().trim().min(1).max(100) }).strict().optional() }).strict();
const requestSchema = z.object({ name: z.enum(['prope_connection_status', 'prope_search_prompts', 'prope_get_revision', 'prope_prepare_capture', 'prope_prepare_revision', 'prope_prepare_evaluation', 'prope_get_evaluation', 'prope_open_panel']), arguments: z.record(z.string(), z.unknown()).default({}) }).strict();
const revisionRead = z.object({ prompt_id: z.string(), version_id: z.string() }).strict();
const evalRead = z.object({ prompt_id: z.string(), original_run_id: z.string(), candidate_run_id: z.string() }).strict();

export class Broker {
  private readonly pairs = new Map<string, Pair>();
  private readonly grants = new Map<string, Pair>();
  private readonly server = createServer((request, response) => {
    void this.handle(request).then((data) => { response.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }); response.end(JSON.stringify(data)); })
      .catch((error: unknown) => { response.writeHead(error instanceof ConnectorError ? error.status : 400, { 'Content-Type': 'application/json' }); response.end(JSON.stringify({ error: error instanceof ConnectorError ? error.code : 'invalid_request' })); });
  });
  port = 0;
  private readonly expiryTimer = setInterval(() => this.expire(), 10_000);
  open: () => void = () => undefined;
  constructor(readonly api: ManagementApi, readonly proposals: Proposals) {}
  async start() {
    this.expiryTimer.unref(); this.server.requestTimeout = 5000;
    await new Promise<void>((resolve, reject) => { this.server.once('error', reject); this.server.listen(0, '127.0.0.1', resolve); });
    const address = this.server.address();
    if (!address || typeof address === 'string') throw new ConnectorError('broker_unavailable');
    this.port = address.port;
  }
  pending() { this.expire(); return [...this.pairs.values()].filter((pair) => !pair.token); }
  async connections() {
    const session = await this.api.session();
    if (!session.user.workspace_id || session.must_change_password) throw new ConnectorError('workspace_required', 403);
    this.expire();
    if ([...this.grants.values()].some((grant) => grant.workspace !== session.user.workspace_id || grant.actor !== session.user.id)) {
      this.revoke(); throw new ConnectorError('session_changed', 401);
    }
    return [...this.pairs.values()].map((pair) => ({
      connection_id: pair.code, client_name: pair.client?.name.replace(/[$\p{Cc}\p{Cf}]/gu, '') || null,
      status: !pair.token ? 'pending' as const : pair.heartbeat === undefined ? 'awaiting_client' as const : 'connected' as const,
      namespace: pair.namespace ?? null, heartbeat_at: pair.heartbeat ?? null,
      conversations: [...(pair.conversations?.values() ?? [])].sort((a, b) => b.last_seen - a.last_seen),
      conversation_history_limited: pair.conversationHistoryLimited ?? false,
    }));
  }
  async check(connectionId: string) {
    await this.connections();
    const pair = [...this.pairs.values()].find((entry) => entry.code === connectionId);
    if (!pair?.token) throw new ConnectorError('pair_required', 401);
    const baseline = pair.heartbeat; const deadline = Date.now() + 25_000;
    while (true) {
      this.expire();
      if (this.pairs.get(pair.ticket) !== pair) throw new ConnectorError('pair_expired', 401);
      if (pair.heartbeat !== undefined && pair.heartbeat !== baseline) return { connection_id: pair.code, heartbeat_at: pair.heartbeat };
      if (Date.now() >= deadline) throw new ConnectorError('heartbeat_timeout', 504);
      await new Promise<void>((resolve) => setTimeout(resolve, 250));
    }
  }
  async conversationTitle(connectionId: string, threadId: string, read: (id: string) => Promise<ConversationTitle>) {
    return this.withCodexConversation(connectionId, threadId, read);
  }
  async chooseConversation(connectionId: string, choose: () => Promise<string | undefined>) {
    await this.connections();
    const pair = [...this.pairs.values()].find((entry) => entry.code === connectionId);
    if (!pair?.token) throw new ConnectorError('pair_required', 401);
    if (pair.client?.name !== 'codex-mcp-client') throw new ConnectorError('codex_title_unsupported_client');
    const token = pair.token; const selected = await choose();
    await this.connections();
    if (this.pairs.get(pair.ticket) !== pair || pair.token !== token) throw new ConnectorError('pair_expired', 401);
    if (selected) this.observe(pair, conversationIdSchema.parse(selected), 'user_selected_codex_thread');
    return { selected: Boolean(selected) };
  }
  private observe(pair: Pair, threadId: string, source: ConversationObservation['source']) {
    const observations = pair.conversations ?? new Map<string, ConversationObservation>();
    const previous = observations.get(threadId); const now = Date.now();
    if (!previous && observations.size >= 32) {
      const oldest = [...observations.values()].sort((a, b) => a.last_seen - b.last_seen)[0];
      if (oldest) observations.delete(oldest.thread_id);
      pair.conversationHistoryLimited = true;
    }
    observations.set(threadId, { thread_id: threadId, source: previous?.source === 'mcp_metadata_thread_id' ? previous.source : source, first_seen: previous?.first_seen ?? now, last_seen: now });
    pair.conversations = observations;
  }
  async withCodexConversation<T>(connectionId: string, threadId: string, read: (id: string) => Promise<T>) {
    await this.connections();
    const pair = [...this.pairs.values()].find((entry) => entry.code === connectionId);
    if (!pair?.token || !pair.conversations?.has(threadId)) throw new ConnectorError('scope_denied', 403);
    if (pair.client?.name !== 'codex-mcp-client') throw new ConnectorError('codex_title_unsupported_client');
    const token = pair.token;
    const result = await read(threadId);
    await this.connections();
    if (this.pairs.get(pair.ticket) !== pair || pair.token !== token || !pair.conversations.has(threadId)) throw new ConnectorError('pair_expired', 401);
    return result;
  }
  async approve(code: string, namespace: string) {
    this.expire(); const pair = this.pending().find((item) => item.code === code);
    if (!pair) throw new ConnectorError('pair_expired');
    const session = await this.api.session();
    if (!session.user.workspace_id || session.must_change_password) throw new ConnectorError('workspace_required');
    if (this.pairs.get(pair.ticket) !== pair || pair.token || pair.expires < Date.now()) throw new ConnectorError('pair_expired');
    pair.workspace = session.user.workspace_id; pair.actor = session.user.id; pair.namespace = namespace;
    pair.token = randomBytes(32).toString('hex'); pair.expires = Date.now() + 8 * 60 * 60_000; pair.lease = Date.now() + 60_000;
    this.grants.set(pair.token, pair);
  }
  revoke() { this.pairs.clear(); this.grants.clear(); this.proposals.clear(); }
  close() { clearInterval(this.expiryTimer); this.revoke(); this.server.close(); }
  private expire() {
    for (const [ticket, pair] of this.pairs) if (pair.expires < Date.now() || (pair.lease !== undefined && pair.lease < Date.now())) { this.pairs.delete(ticket); if (pair.token) { this.grants.delete(pair.token); this.proposals.clear(pair.ticket); } }
  }
  private async body(request: IncomingMessage) {
    request.setEncoding('utf8');
    let body = ''; let bytes = 0;
    for await (const chunk of request) { const value = String(chunk); bytes += Buffer.byteLength(value); if (bytes > 160_000) throw new ConnectorError('payload_too_large', 413); body += value; }
    return JSON.parse(body || '{}') as unknown;
  }
  private async handle(request: IncomingMessage): Promise<unknown> {
    const requestId = randomUUID(); const start = performance.now();
    if (request.method !== 'POST' || request.headers.origin || request.headers.host !== `127.0.0.1:${this.port}`) throw new ConnectorError('forbidden', 403);
    this.expire(); const body = await this.body(request);
    if (request.url === '/pair/start') {
      const input = pairStartSchema.parse(body);
      if (this.pairs.size >= 8) throw new ConnectorError('pair_limit', 429);
      const pair: Pair = { ticket: randomBytes(32).toString('hex'), code: randomBytes(4).toString('hex').toUpperCase(), expires: Date.now() + 120_000, client: input.client };
      this.pairs.set(pair.ticket, pair); return { ticket: pair.ticket, code: pair.code };
    }
    if (request.url === '/pair/status') {
      const { ticket } = z.object({ ticket: z.string().length(64) }).strict().parse(body); const pair = this.pairs.get(ticket);
      if (!pair) throw new ConnectorError('pair_expired', 401);
      return { code: pair.code, token: pair.token ?? null };
    }
    if (request.url === '/pair/observe') {
      const input = z.object({ ticket: z.string().length(64), thread_id: conversationIdSchema }).strict().parse(body);
      const pair = this.pairs.get(input.ticket);
      if (!pair) throw new ConnectorError('pair_expired', 401);
      this.observe(pair, input.thread_id, 'mcp_metadata_thread_id');
      return { observed: true };
    }
    const presented = request.headers.authorization?.replace(/^Bearer /, '') ?? '';
    const grant = [...this.grants.entries()].find(([token]) => token.length === presented.length && timingSafeEqual(Buffer.from(token), Buffer.from(presented)))?.[1];
    if (!grant) throw new ConnectorError('pair_required', 401);
    const session = await this.api.session();
    if (session.user.workspace_id !== grant.workspace || session.user.id !== grant.actor || session.must_change_password) { this.revoke(); throw new ConnectorError('session_changed', 401); }
    grant.lease = Date.now() + 60_000;
    if (request.url === '/heartbeat') { grant.heartbeat = Date.now(); return { connected: true }; }
    if (request.url === '/disconnect') { if (grant.token) this.grants.delete(grant.token); this.pairs.delete(grant.ticket); this.proposals.clear(grant.ticket); return { disconnected: true }; }
    if (request.url !== '/tool') throw new ConnectorError('not_found', 404);
    const call = requestSchema.parse(body);
    try { return await this.tool(grant, call.name, call.arguments); }
    finally { console.error(JSON.stringify({ event: 'connector.tool', request_id: requestId, connection_id: grant.code, tool: call.name.slice(0, 80), latency_ms: Math.round(performance.now() - start) })); }
  }
  private async readable(grant: Pair, promptId: string) {
    const prompt = await this.api.prompt(promptId);
    if (prompt.namespace !== grant.namespace) throw new ConnectorError('scope_denied', 403);
    return prompt;
  }
  async tool(grant: Pair, name: string, args: Record<string, unknown>): Promise<unknown> {
    if (name === 'prope_connection_status') {
      const receipt = z.object({ prompt_id: z.string().optional(), version_id: z.string().optional(), original_run_id: z.string().optional(), candidate_run_id: z.string().optional(), suite_id: z.string().optional() });
      return { connected: true, workspace_id: grant.workspace, namespace: grant.namespace,
        proposals: this.proposals.list().filter((entry) => entry.connection_id === grant.ticket).map((entry) => ({
          proposal_id: entry.id, status: entry.status, result: receipt.safeParse(entry.result).success ? receipt.parse(entry.result) : null,
        })) };
    }
    if (name === 'prope_open_panel') { this.open(); return { opened: true }; }
    if (name === 'prope_search_prompts') {
      const { query = '' } = z.object({ query: z.string().max(200).optional() }).strict().parse(args);
      const prompts = z.array(promptSchema).parse(await this.api.request(`/api/v1/prompts?q=${encodeURIComponent(query)}&limit=200`));
      return prompts.filter((prompt) => prompt.namespace === grant.namespace);
    }
    if (name === 'prope_get_revision') {
      const input = revisionRead.parse(args); await this.readable(grant, input.prompt_id);
      const revision = await this.api.revision(input.version_id);
      if (revision.prompt_id !== input.prompt_id) throw new ConnectorError('scope_denied', 403);
      return revision;
    }
    if (name === 'prope_prepare_capture') { const input = captureSchema.parse(args); this.open(); return this.proposals.add(grant.ticket, { kind: 'capture', ...input }, grant.namespace ?? ''); }
    if (name === 'prope_prepare_revision') {
      const input = revisionProposalSchema.parse(args); await this.readable(grant, input.prompt_id);
      const revision = await this.api.revision(input.base_version_id);
      if (revision.prompt_id !== input.prompt_id) throw new ConnectorError('scope_denied', 403);
      this.open(); return this.proposals.add(grant.ticket, { kind: 'revision', ...input }, grant.namespace ?? '');
    }
    if (name === 'prope_prepare_evaluation') {
      const input = evaluationProposalSchema.parse(args); await this.readable(grant, input.prompt_id);
      this.open(); return this.proposals.addEvaluation(grant.ticket, { kind: 'evaluation', ...input }, grant.namespace ?? '');
    }
    if (name === 'prope_get_evaluation') {
      const input = evalRead.parse(args); await this.readable(grant, input.prompt_id);
      return this.api.request(`/api/v1/prompts/${encodeURIComponent(input.prompt_id)}/eval-comparisons?${new URLSearchParams({ original_run_id: input.original_run_id, candidate_run_id: input.candidate_run_id })}`);
    }
    throw new ConnectorError('unknown_tool', 404);
  }
  namespace(connectionId: string) { this.expire(); return this.pairs.get(connectionId)?.namespace; }
}
