import { z } from 'zod';

/**
 * The wire contract for `/api/v1/chat/*`.
 *
 * Parsed rather than cast, for the reason every other feature here parses: the
 * assistant's reply is the one payload in this product that a language model
 * had a hand in, and a client that trusted its shape would be trusting the
 * least trustworthy producer in the system. The server validates it too; this
 * is the second wall, not the first.
 */

/**
 * The closed directive vocabulary, mirrored from `chat_orchestrator/domain.py`.
 *
 * A discriminated union rather than `{kind: string, arguments: unknown}`, so
 * that a directive the server invents — or one an older client does not know —
 * fails its branch and is dropped by {@link uiDirectiveSchema}'s catch below
 * instead of reaching a `switch` with no case for it.
 */
export const uiDirectiveSchema = z.discriminatedUnion('kind', [
  z.object({ kind: z.literal('navigate'), arguments: z.object({ to: z.string() }) }),
  z.object({ kind: z.literal('open_panel'), arguments: z.object({ panel: z.enum(['home', 'chat', 'search', 'notifications']) }) }),
  z.object({ kind: z.literal('select_tab'), arguments: z.object({ tab: z.string() }) }),
  z.object({ kind: z.literal('prefill_form'), arguments: z.object({ form: z.string(), fields: z.record(z.string(), z.string()) }) }),
  z.object({ kind: z.literal('highlight'), arguments: z.object({ target: z.string() }) }),
  z.object({ kind: z.literal('open_dialog'), arguments: z.object({ dialog: z.string() }) }),
  z.object({ kind: z.literal('set_step'), arguments: z.object({ step: z.string() }) }),
]);

export type UiDirective = z.infer<typeof uiDirectiveSchema>;

/** Unknown kinds are dropped, never thrown: the reply is the answer, the directives are the extra. */
const directiveListSchema = z.array(z.unknown()).transform((items) =>
  items.flatMap((item) => {
    const parsed = uiDirectiveSchema.safeParse(item);
    return parsed.success ? [parsed.data] : [];
  }),
);

export const traceEntrySchema = z.object({
  agent: z.string(),
  action: z.string(),
  status: z.enum(['ok', 'warn', 'error']).catch('ok'),
  latency_ms: z.number(),
  detail: z.record(z.string(), z.unknown()).default({}),
});

export const citationSchema = z.object({
  kind: z.string(),
  reference: z.string(),
  label: z.string(),
  score: z.number().nullable().default(null),
});

export const pendingActionSchema = z.object({
  id: z.string(),
  tool: z.string(),
  summary: z.string(),
  preview: z.record(z.string(), z.unknown()).default({}),
});

export const turnSchema = z.object({
  conversation_id: z.string(),
  message_id: z.string(),
  intent: z.string(),
  reply: z.string().default(''),
  code: z.string().nullable().default(null),
  outcome: z.string(),
  degraded: z.array(z.string()).default([]),
  trace: z.array(traceEntrySchema).default([]),
  citations: z.array(citationSchema).default([]),
  directives: directiveListSchema.default([]),
  pending: pendingActionSchema.nullable().default(null),
});

export const actionDecisionSchema = z.object({
  id: z.string(),
  status: z.string(),
  code: z.string().nullable().default(null),
  prompt_id: z.string().nullable().default(null),
  version_id: z.string().nullable().default(null),
  directives: directiveListSchema.default([]),
});

export const conversationSchema = z.object({
  id: z.string(),
  title_code: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
  message_count: z.number(),
});

export const conversationListSchema = z.object({ conversations: z.array(conversationSchema).default([]) });

export const messageSchema = z.object({
  id: z.string(),
  role: z.enum(['user', 'agent']),
  text: z.string(),
  intent: z.string().nullable().default(null),
  created_at: z.string(),
  trace: z.array(traceEntrySchema).default([]),
  citations: z.array(citationSchema).default([]),
  directives: directiveListSchema.default([]),
});

export const transcriptSchema = z.object({
  conversation: conversationSchema,
  messages: z.array(messageSchema).default([]),
  pending: pendingActionSchema.nullable().default(null),
});

export type TraceEntry = z.infer<typeof traceEntrySchema>;
export type Citation = z.infer<typeof citationSchema>;
export type PendingAction = z.infer<typeof pendingActionSchema>;
export type Turn = z.infer<typeof turnSchema>;
export type ActionDecision = z.infer<typeof actionDecisionSchema>;
export type Conversation = z.infer<typeof conversationSchema>;
export type Transcript = z.infer<typeof transcriptSchema>;

/** What the panel renders. One entry per turn, either side of the conversation. */
export interface ChatMessage {
  id: string;
  role: 'user' | 'agent';
  /** Generated prose. Empty on a refusal, where `code` carries the catalogue key instead. */
  text: string;
  /** A machine code the client translates (ADR-0053). Never a display string from the server. */
  code?: string | null;
  citations?: Citation[];
  trace?: TraceEntry[];
  degraded?: string[];
  pending?: PendingAction | null;
  /** Set once the person has decided, so the card stops offering buttons. */
  settled?: 'confirmed' | 'rejected';
}

/** The four formats the assistant will convert. `xml` is deliberately not one. */
export type AttachmentFormat = 'txt' | 'md' | 'markdown' | 'json' | 'yaml';
