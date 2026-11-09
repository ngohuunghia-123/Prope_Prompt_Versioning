import { spawn } from 'node:child_process';
import { z } from 'zod';
import { conversationIdSchema, type ConversationTitle } from '@connector/contracts';
import { ConnectorError } from './api';

const responseSchema = z.object({ thread: z.object({ id: conversationIdSchema, name: z.string().max(1000).nullable().optional() }) });
let reading = false;

export async function readCodexThreadTitle(binary: string, threadId: string): Promise<ConversationTitle> {
  conversationIdSchema.parse(threadId);
  if (reading) throw new ConnectorError('operation_in_progress');
  reading = true;
  try { return await readMetadata(binary, threadId); }
  finally { reading = false; }
}

function readMetadata(binary: string, threadId: string): Promise<ConversationTitle> {
  return readCodexThread(binary, threadId, false, (raw) => {
    const data = responseSchema.parse(raw);
    if (data.thread.id !== threadId) throw new Error('thread_mismatch');
    return { thread_id: threadId, title: data.thread.name?.trim() ? data.thread.name : null, source: 'codex_thread_read', checked_at: Date.now() };
  });
}

export function readCodexThread<T>(binary: string, threadId: string, includeTurns: boolean, decode: (raw: unknown) => T): Promise<T> {
  conversationIdSchema.parse(threadId);
  return readCodexMetadata(binary, 'thread/read', { threadId, includeTurns }, decode);
}

export function readCodexMetadata<T>(binary: string, method: 'thread/read' | 'thread/list', params: Record<string, unknown>, decode: (raw: unknown) => T): Promise<T> {
  return withCodexReader(binary, async (read) => decode(await read(method, params)));
}

type ReadMethod = 'thread/read' | 'thread/list' | 'thread/turns/list';
type CodexRead = (method: ReadMethod, params: Record<string, unknown>) => Promise<unknown>;
const frameSchema = z.object({ id: z.union([z.string(), z.number()]).optional(), result: z.unknown().optional(), error: z.unknown().optional() });

export async function withCodexReader<T>(binary: string, run: (read: CodexRead) => Promise<T>, kind: 'title' | 'session' = 'title'): Promise<T> {
  const child = spawn(binary, ['app-server', '--stdio'], { windowsHide: true, stdio: ['pipe', 'pipe', 'ignore'] });
  const prefix = kind === 'session' ? 'session_history' : 'codex_title';
  const tooLarge = () => new ConnectorError(kind === 'session' ? 'session_history_too_large' : 'codex_title_response_too_large', 413);
  let failure: ConnectorError | undefined; let closed = false; let serial = 0;
  let buffer = ''; let frameBytes = 0; let total = 0; let oversized = false;
  let pending: { id: string; method: string; resolve: (raw: unknown) => void; reject: (error: ConnectorError) => void } | undefined;
  const abort = (error: ConnectorError) => { failure ??= error; pending?.reject(error); pending = undefined; };
  const timeout = setTimeout(() => abort(new ConnectorError(`${prefix}_timeout`, 504)), kind === 'session' ? 30_000 : 15_000);
  const send = (message: object) => child.stdin.write(`${JSON.stringify(message)}\n`);
  const request = (method: string, params: Record<string, unknown>) => new Promise<unknown>((resolve, reject) => {
    if (failure) { reject(failure); return; }
    if (pending) { reject(new ConnectorError('operation_in_progress')); return; }
    const id = `prope-read-${serial++}`;
    pending = { id, method, resolve, reject }; send({ id, method, params });
  });
  child.on('error', () => abort(new ConnectorError(`${prefix}_unavailable`)));
  child.stdin.on('error', () => { if (!closed) abort(new ConnectorError(`${prefix}_unavailable`)); });
  child.on('exit', () => { if (!closed) abort(new ConnectorError(`${prefix}_unavailable`)); });
  child.stdout.setEncoding('utf8');
  child.stdout.on('data', (chunk: string) => {
    if (closed || failure) return;
    total += Buffer.byteLength(chunk);
    if (total > (kind === 'session' ? 32_000_000 : 2_000_000)) { abort(tooLarge()); return; }
    let start = 0;
    while (start < chunk.length && !failure) {
      const newline = chunk.indexOf('\n', start);
      const part = chunk.slice(start, newline < 0 ? undefined : newline);
      frameBytes += Buffer.byteLength(part);
      if (frameBytes > 2_000_000) { oversized = true; buffer = ''; }
      else if (!oversized) buffer += part;
      if (newline < 0) break;
      // Discard an oversized frame without retaining it, then retry a smaller read-only page.
      if (oversized) { const current = pending; pending = undefined; current?.reject(tooLarge()); }
      else {
        try {
          const frame = frameSchema.parse(JSON.parse(buffer));
          if (pending && frame.id === pending.id) {
            const current = pending; pending = undefined;
            if (frame.error !== undefined || frame.result === undefined) {
              const unsupported = current.method === 'thread/turns/list' && z.object({ code: z.literal(-32601) }).safeParse(frame.error).success;
              current.reject(new ConnectorError(unsupported ? 'session_history_pagination_unsupported' : `${prefix}_unavailable`));
            } else current.resolve(frame.result);
          }
        } catch { abort(new ConnectorError(`${prefix}_unavailable`)); }
      }
      buffer = ''; frameBytes = 0; oversized = false; start = newline + 1;
    }
  });
  try {
    await request('initialize', { clientInfo: { name: 'prope_title_reader', version: '0.1.0' } });
    send({ method: 'initialized' });
    const value = await run(request);
    if (failure) throw failure;
    return value;
  } catch (error) { throw error instanceof ConnectorError ? error : new ConnectorError(`${prefix}_unavailable`); }
  finally {
    closed = true; clearTimeout(timeout); child.stdin.end();
    if (child.exitCode === null) {
      const cleanup = setTimeout(() => child.kill(), 1000); cleanup.unref();
      child.once('exit', () => clearTimeout(cleanup));
    }
  }
}
