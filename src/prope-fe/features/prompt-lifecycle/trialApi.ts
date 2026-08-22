import { ApiError } from '@/lib/apiClient';

/**
 * The playground turn: post the thread, read the stream.
 *
 * **Not `apiRequest`, and that is the whole reason this file exists.** That
 * helper reads the whole body and parses it as JSON, which for an event stream
 * means waiting for the last byte and then failing to parse it. Everything else
 * it does — `credentials: 'include'`, the error-envelope shape, the 401 handler —
 * is reproduced below so that a trial refuses exactly like every other call.
 */

const dataMode =
  import.meta.env.VITE_DATA_MODE ??
  import.meta.env.VITE_AUTH_MODE ??
  'api';
const useRealApi = dataMode === 'api';

export function trialsAreLive(): boolean {
  return useRealApi;
}

export interface TrialTurn {
  role: 'user' | 'assistant';
  content: string;
}

export interface TrialError {
  /** A closed token from provider-access — `rate_limited`, `credential_rejected`, … */
  errorClass: string;
  message: string;
  retryable: boolean;
}

/**
 * What one turn cost. Arrives once, as the last event before the terminator.
 *
 * `cost` is a **string** on the wire and stays one here: the server computes it as
 * a ten-place `Decimal` with the same two functions the ledger will use, and
 * `JSON.parse` on a bare number would round it in the places a reconciliation
 * would compare. `null` means the workspace has no price row for this
 * `(provider, model)` pair — unpriced, which is not the same as free and is never
 * rendered as zero.
 */
export interface TrialUsage {
  callId: string;
  inputTokens: number | null;
  outputTokens: number | null;
  cost: string | null;
  currency: string | null;
  outcome: string;
  upstreamDurationMs: number | null;
  upstreamModel: string | null;
}

/** The sampling controls the playground may set. A closed set, mirroring the server's. */
export interface TrialParameters {
  temperature?: number;
  top_p?: number;
  max_tokens?: number;
  presence_penalty?: number;
  frequency_penalty?: number;
}

export interface TrialInput {
  messages: TrialTurn[];
  variables: Record<string, string>;
  /** Both halves or neither — the server refuses a half-binding with a 422. */
  providerConfigId?: string;
  upstreamModel?: string;
  parameters?: TrialParameters;
}

export interface TrialHandlers {
  /** Called once per text delta, with the delta only — never the accumulation. */
  onDelta: (text: string) => void;
  /** Called once, on the first chunk, with what the server says it served. */
  onIdentity?: (identity: { callId: string; versionId: string; revisionNumber: number }) => void;
  /** Called once, at the end, with the tokens and the cost the ledger will record. */
  onUsage?: (usage: TrialUsage) => void;
  /** An in-band failure. The stream is over; nothing further arrives. */
  onError?: (error: TrialError) => void;
}

interface UsageEnvelope {
  call_id?: string;
  input_tokens?: number | null;
  output_tokens?: number | null;
  cost?: string | null;
  currency?: string | null;
  outcome?: string;
  upstream_duration_ms?: number | null;
  upstream_model?: string | null;
}

interface PropeEnvelope {
  call_id?: string;
  version_id?: string;
  revision_number?: number;
  error?: { class?: string; message?: string; retryable?: boolean };
  usage?: UsageEnvelope;
}

interface TrialChunk {
  choices?: { delta?: { content?: string } }[];
  prope?: PropeEnvelope;
}

const errorShape = (payload: unknown): TrialError | null => {
  const error = (payload as TrialChunk | undefined)?.prope?.error;
  if (!error) return null;
  return {
    errorClass: String(error.class ?? 'unknown'),
    message: String(error.message ?? ''),
    retryable: Boolean(error.retryable),
  };
};

/**
 * Run one turn. Resolves when the stream ends; rejects only on a **pre-flight**
 * refusal — an unbound revision, an unfilled variable, an oversize thread, a
 * spend ceiling — because once the server has begun streaming its status line is
 * already 200 and a failure can only arrive as an in-band event on `onError`.
 * That split is the same one the gateway makes, and a client written for one is
 * written for the other.
 *
 * `signal` aborts the read. The server-side dispatch is not cancelled by it and
 * the ledger row is still written: the tokens were generated and somebody paid
 * for them, so a record that vanished because a person closed a tab would make
 * the workspace's spend total wrong.
 */
export async function runTrial(
  promptId: string,
  versionId: string,
  input: TrialInput,
  handlers: TrialHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(
    `/api/v1/prompts/${encodeURIComponent(promptId)}/revisions/${encodeURIComponent(versionId)}/trials`,
    {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({
        messages: input.messages,
        variables: input.variables,
        // Omitted rather than sent as null when untouched: the server reads
        // "absent" as "use the revision's", and `extra="forbid"` means a field
        // this API does not know is a 422 rather than a silent ignore.
        ...(input.providerConfigId && input.upstreamModel
          ? { provider_config_id: input.providerConfigId, upstream_model: input.upstreamModel }
          : {}),
        ...(input.parameters && Object.keys(input.parameters).length > 0
          ? { parameters: input.parameters }
          : {}),
      }),
      signal,
    },
  );

  if (!response.ok) {
    const payload = (await response.json().catch(() => undefined)) as
      | { error?: { code?: string; message?: string; request_id?: string } }
      | undefined;
    throw new ApiError(
      response.status,
      payload?.error?.code ?? 'UNEXPECTED_RESPONSE',
      payload?.error?.message ?? response.statusText,
      payload?.error?.request_id,
    );
  }

  const body = response.body;
  if (!body) return;

  const reader = body.pipeThrough(new TextDecoderStream()).getReader();
  // SSE frames are separated by a blank line and can be split across network
  // reads, so a partial frame is carried forward rather than parsed. Dropping
  // this buffer is the classic way to lose one token in twenty under load.
  let buffered = '';
  let identified = false;

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffered += value;

      let boundary = buffered.indexOf('\n\n');
      while (boundary !== -1) {
        const frame = buffered.slice(0, boundary);
        buffered = buffered.slice(boundary + 2);
        boundary = buffered.indexOf('\n\n');

        const line = frame.split('\n').find((candidate) => candidate.startsWith('data:'));
        if (!line) continue;
        const data = line.slice('data:'.length).trim();
        if (data === '[DONE]') return;

        let chunk: TrialChunk;
        try {
          chunk = JSON.parse(data) as TrialChunk;
        } catch {
          // A frame we cannot parse is a frame we cannot render. Skipping it keeps
          // the rest of the turn readable, which is better than discarding the
          // answer over one malformed delta.
          continue;
        }

        const failure = errorShape(chunk);
        if (failure) {
          handlers.onError?.(failure);
          return;
        }

        // The meter. Read before the delta loop and then `continue`, because a
        // usage event carries no `choices` and falling through would be a lap of
        // an empty array — harmless, but it would read as if it might not be.
        const usage = chunk.prope?.usage;
        if (usage) {
          handlers.onUsage?.({
            callId: usage.call_id ?? '',
            inputTokens: usage.input_tokens ?? null,
            outputTokens: usage.output_tokens ?? null,
            cost: usage.cost ?? null,
            currency: usage.currency ?? null,
            outcome: usage.outcome ?? 'ok',
            upstreamDurationMs: usage.upstream_duration_ms ?? null,
            upstreamModel: usage.upstream_model ?? null,
          });
          continue;
        }

        if (!identified && chunk.prope?.call_id) {
          identified = true;
          handlers.onIdentity?.({
            callId: chunk.prope.call_id,
            versionId: chunk.prope.version_id ?? versionId,
            revisionNumber: chunk.prope.revision_number ?? 0,
          });
        }

        for (const choice of chunk.choices ?? []) {
          const text = choice.delta?.content;
          if (text) handlers.onDelta(text);
        }
      }
    }
  } finally {
    // Releasing matters on the abort path: an un-released reader keeps the
    // response body — and its socket — alive for as long as the page is open.
    reader.releaseLock();
  }
}

/**
 * The `{{variable}}` names a body needs, in first-appearance order.
 *
 * **The same pattern the server renders with** (`prope.prompt_composition`),
 * duplicated here for one reason: the screen has to draw an input per variable
 * *before* it sends anything, and asking the server what it will demand would be
 * a round trip to learn something already in the body the page has loaded. The
 * server remains the authority — an unfilled placeholder is refused there — so
 * the worst a drift costs is a refusal the person can read.
 */
const PLACEHOLDER = /\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}/g;

export function requiredVariables(body: string): string[] {
  const seen: string[] = [];
  for (const match of body.matchAll(PLACEHOLDER)) {
    const name = match[1];
    if (name && !seen.includes(name)) seen.push(name);
  }
  return seen;
}
