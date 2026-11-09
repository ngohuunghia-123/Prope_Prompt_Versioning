import { z } from 'zod';
import { ApiError, setApiTransport } from '@/lib/apiClient';

declare function acquireVsCodeApi(): { postMessage(message: unknown): void };
const host = acquireVsCodeApi();
const pending = new Map<string, { resolve: (value: unknown) => void; reject: (error: Error) => void; timer: ReturnType<typeof setTimeout> }>();
const responseSchema = z.object({ type: z.literal('response'), id: z.string(), ok: z.boolean(), data: z.unknown().optional(), error: z.object({ code: z.string(), request_id: z.string().optional() }).optional() });
let changed: (reset: boolean) => void = () => undefined;
export function onHostChanged(handler: (reset: boolean) => void) { changed = handler; }
window.addEventListener('message', (event: MessageEvent<unknown>) => {
  const notification = z.object({ type: z.literal('changed'), reset: z.boolean().optional() }).safeParse(event.data);
  if (notification.success) { changed(notification.data.reset ?? false); return; }
  const parsed = responseSchema.safeParse(event.data); if (!parsed.success) return;
  const response = parsed.data; const call = pending.get(response.id); if (!call) return;
  clearTimeout(call.timer); pending.delete(response.id);
  if (response.ok) call.resolve(response.data);
  else call.reject(new ApiError(400, response.error?.code ?? 'invalid_response', response.error?.code ?? 'invalid_response', response.error?.request_id));
});
export function callHost(action: string, payload?: unknown): Promise<unknown> {
  const id = crypto.randomUUID();
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(new ApiError(504, 'outcome_unknown', 'outcome_unknown')); }, 180_000);
    pending.set(id, { resolve, reject, timer }); host.postMessage({ id, action, payload });
  });
}
setApiTransport(async (input, init) => {
  if (input === '/api/v1/datasets' && init?.method === 'POST' && typeof init.body === 'string') {
    const data = await callHost('create_dataset', JSON.parse(init.body) as unknown);
    return new Response(JSON.stringify(data), { status: 201, headers: { 'Content-Type': 'application/json' } });
  }
  if (typeof input !== 'string' || (init?.method && init.method !== 'GET')) throw new ApiError(403, 'read_denied', 'read_denied');
  const data = await callHost('read', input);
  return new Response(JSON.stringify(data), { status: 200, headers: { 'Content-Type': 'application/json' } });
});
