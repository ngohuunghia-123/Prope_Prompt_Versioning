import { randomUUID } from 'node:crypto';
import { z } from 'zod';

export interface SecretStore { get(key: string): Thenable<string | undefined>; store(key: string, value: string): Thenable<void>; delete(key: string): Thenable<void>; }
export const sessionSchema = z.object({
  expires_at: z.string(), must_change_password: z.boolean(),
  user: z.object({ id: z.string(), workspace_id: z.string().nullable(), workspace_name: z.string().nullable() }),
});
export const promptSchema = z.object({ prompt_id: z.string(), namespace: z.string(), name: z.string(), title: z.string(), model_name: z.string() });
export const revisionSchema = z.object({
  version_id: z.string(), prompt_id: z.string(), body: z.string(), original_body: z.string(),
  provider_config_id: z.string().nullable(), upstream_model: z.string().nullable(),
  parameters: z.record(z.string(), z.unknown()), created_at: z.string(),
  route_combo_id: z.string().nullable().optional(),
  fallback_answer: z.string().nullable().optional(),
});
export class ConnectorError extends Error {
  constructor(public readonly code: string, public readonly status = 400, public readonly requestId?: string) { super(code); }
}

export class ManagementApi {
  onInvalidated: () => void = () => undefined;
  private cookie: string | undefined;
  private readonly key: string;
  constructor(private readonly secrets: SecretStore, readonly baseUrl: string, private readonly log: (event: object) => void) {
    const url = new URL(baseUrl);
    if (!['127.0.0.1', '[::1]'].includes(url.hostname) || url.protocol !== 'http:' || url.username || url.password || url.pathname !== '/' || url.search || url.hash) throw new ConnectorError('loopback_backend_required');
    this.key = `prope.connector.session:${url.origin}`;
  }
  async restore() { this.cookie = await this.secrets.get(this.key); }
  async clear() { this.cookie = undefined; await this.secrets.delete(this.key); this.onInvalidated(); }
  async request(path: string, method = 'GET', body?: unknown, timeoutMs = 45000): Promise<unknown> {
    if (!path.startsWith('/api/v1/') || /[\r\n\\]/.test(path)) throw new ConnectorError('invalid_path');
    const requestId = randomUUID();
    const start = performance.now();
    const requestCookie = this.cookie;
    try {
      const response = await fetch(new URL(path, this.baseUrl), {
        method, redirect: 'error', signal: AbortSignal.timeout(timeoutMs),
        headers: { 'Content-Type': 'application/json', 'X-Request-ID': requestId, ...(requestCookie ? { Cookie: requestCookie } : {}) },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      this.log({ event: 'connector.api', request_id: requestId, status: response.status, latency_ms: Math.round(performance.now() - start) });
      if (method === 'GET' && requestCookie && this.cookie !== requestCookie) throw new ConnectorError('session_changed', 409, requestId);
      // Anonymous polling and late failures from an old session must not revoke
      // pending pairings or erase a session established by a newer login.
      if (response.status === 401 && requestCookie && this.cookie === requestCookie) await this.clear();
      if (!response.ok) {
        const parsed = z.object({ error: z.object({ code: z.string(), request_id: z.string().optional() }) }).safeParse(await response.json().catch(() => null));
        throw new ConnectorError(parsed.success ? parsed.data.error.code : 'api_error', response.status, parsed.success ? parsed.data.error.request_id : requestId);
      }
      for (const value of response.headers.getSetCookie()) {
        const cookie = value.split(';')[0];
        if (cookie?.startsWith('prope_session=')) { this.cookie = cookie; await this.secrets.store(this.key, cookie); }
      }
      return response.status === 204 ? null : await response.json();
    } catch (error) {
      if (error instanceof ConnectorError) throw error;
      this.log({ event: 'connector.api_error', request_id: requestId, latency_ms: Math.round(performance.now() - start) });
      throw new ConnectorError(method === 'GET' ? 'connection_failed' : 'write_outcome_unknown', 503, requestId);
    }
  }
  async session() { return sessionSchema.parse(await this.request('/api/v1/auth/session')); }
  async prompt(id: string) { return promptSchema.parse(await this.request(`/api/v1/prompts/${encodeURIComponent(id)}`)); }
  async revision(id: string) { return revisionSchema.parse(await this.request(`/api/v1/revisions/${encodeURIComponent(id)}`)); }
}
