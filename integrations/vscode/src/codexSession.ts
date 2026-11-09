import { z } from 'zod';
import { conversationIdSchema } from '@connector/contracts';
import { sessionMessageSchema } from '@connector/sessionChatContracts';
import { ConnectorError } from './api';
import { withCodexReader } from './codexThreadTitle';

const itemHeader = z.object({ type: z.string() });
const userItem = z.object({ id: z.string(), content: z.array(z.unknown()) });
const agentItem = z.object({ id: z.string(), text: z.string(), phase: z.string().nullable().optional() });
const textPart = z.object({ type: z.literal('text'), text: z.string() });
const historySchema = z.object({ thread: z.object({
  id: conversationIdSchema, name: z.string().max(1000).nullable().optional(),
  turns: z.array(z.object({ items: z.array(z.unknown()), itemsView: z.string().optional() })).max(2000),
}) });

export function decodeCodexSession(raw: unknown, threadId: string) {
  const { thread } = historySchema.parse(raw);
  if (thread.id !== threadId) throw new ConnectorError('thread_mismatch');
  const messages: z.infer<typeof sessionMessageSchema>[] = [];
  for (const turn of thread.turns) {
    if (turn.itemsView && turn.itemsView !== 'full') throw new ConnectorError('session_history_incomplete');
    for (const rawItem of turn.items) {
      const header = itemHeader.parse(rawItem);
      if (header.type === 'userMessage') {
        const item = userItem.parse(rawItem);
        const text = item.content.flatMap((part) => itemHeader.parse(part).type === 'text' ? [textPart.parse(part).text] : []).join('\n');
        if (text) messages.push(sessionMessageSchema.parse({ id: item.id, role: 'user', text }));
      } else if (header.type === 'agentMessage') {
        const item = agentItem.parse(rawItem);
        // Commentary may contain operational details; only answer text is shared.
        if (item.text && (!item.phase || item.phase === 'final_answer')) messages.push(sessionMessageSchema.parse({ id: item.id, role: 'assistant', text: item.text }));
      }
    }
  }
  if (messages.length > 2000 || new Set(messages.map((message) => message.id)).size !== messages.length) throw new ConnectorError('session_history_invalid');
  return { thread_id: thread.id, title: thread.name ?? null, messages };
}

const metadataSchema = z.object({ thread: z.object({ id: conversationIdSchema, name: z.string().max(1000).nullable().optional() }) });
const pageSchema = z.object({
  data: z.array(z.object({ id: z.string().min(1).max(200), items: z.array(z.unknown()), itemsView: z.literal('full') })).max(20),
  nextCursor: z.string().min(1).max(4000).nullable(),
});

export function readCodexSession(binary: string, threadId: string) {
  conversationIdSchema.parse(threadId);
  return withCodexReader(binary, async (read) => {
    const { thread } = metadataSchema.parse(await read('thread/read', { threadId, includeTurns: false }));
    if (thread.id !== threadId) throw new ConnectorError('thread_mismatch');
    const messages: z.infer<typeof sessionMessageSchema>[] = [];
    const turns = new Set<string>(); const ids = new Set<string>(); const cursors = new Set<string>();
    let cursor: string | undefined; let limit = 20; let retainedBytes = 2;
    for (let page = 0; page < 400; page += 1) {
      let raw: unknown;
      try { raw = await read('thread/turns/list', { threadId, limit, sortDirection: 'asc', itemsView: 'full', ...(cursor ? { cursor } : {}) }); }
      catch (error) {
        if (error instanceof ConnectorError && error.code === 'session_history_too_large' && limit > 1) { limit = Math.max(1, Math.floor(limit / 2)); continue; }
        throw error;
      }
      const parsed = pageSchema.safeParse(raw);
      if (!parsed.success) throw new ConnectorError('session_history_incomplete');
      const data = parsed.data;
      if (data.data.length > limit || (!data.data.length && data.nextCursor)) throw new ConnectorError('session_history_invalid');
      for (const turn of data.data) {
        if (turns.has(turn.id)) throw new ConnectorError('session_history_invalid');
        turns.add(turn.id);
        const source = decodeCodexSession({ thread: { ...thread, turns: [turn] } }, threadId);
        for (const message of source.messages) {
          if (ids.has(message.id)) throw new ConnectorError('session_history_invalid');
          ids.add(message.id); retainedBytes += Buffer.byteLength(JSON.stringify(message)) + 1;
          if (retainedBytes > 2_000_000 || ids.size > 2000) throw new ConnectorError('session_history_too_large', 413);
          messages.push(message);
        }
        if (turns.size > 2000) throw new ConnectorError('session_history_too_large', 413);
      }
      if (!data.nextCursor) return { thread_id: threadId, title: thread.name ?? null, messages };
      if (cursors.has(data.nextCursor)) throw new ConnectorError('session_history_invalid');
      cursors.add(data.nextCursor); cursor = data.nextCursor;
    }
    throw new ConnectorError('session_history_too_large', 413);
  }, 'session');
}
