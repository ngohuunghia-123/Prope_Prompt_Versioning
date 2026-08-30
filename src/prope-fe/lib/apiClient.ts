import { z, type ZodType } from 'zod';

const errorEnvelopeSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.unknown().optional(),
    request_id: z.string(),
  }),
});

type UnauthorizedHandler = () => void;
let unauthorizedHandler: UnauthorizedHandler | undefined;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly requestId?: string,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export interface ApiRequestOptions<T> extends RequestInit {
  schema?: ZodType<T>;
  notifyUnauthorized?: boolean;
}

export function setUnauthorizedHandler(handler?: UnauthorizedHandler) {
  unauthorizedHandler = handler;
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export async function apiRequest<T>(path: string, options: ApiRequestOptions<T> = {}): Promise<T> {
  const { schema, notifyUnauthorized = true, ...init } = options;
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const response = await fetch(path, { ...init, headers, credentials: 'include' });

  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => undefined);
    const parsed = errorEnvelopeSchema.safeParse(payload);
    const error = new ApiError(
      response.status,
      parsed.success ? parsed.data.error.code : 'UNEXPECTED_RESPONSE',
      parsed.success ? parsed.data.error.message : response.statusText,
      parsed.success ? parsed.data.error.request_id : undefined,
      parsed.success ? parsed.data.error.details : undefined,
    );
    if (response.status === 401 && notifyUnauthorized) unauthorizedHandler?.();
    throw error;
  }

  if (response.status === 204) return undefined as T;
  const payload: unknown = await response.json();
  return schema ? schema.parse(payload) : payload as T;
}
