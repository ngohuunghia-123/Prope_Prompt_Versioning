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
  index: z.number().default(0),
  mentions: z.array(z.number()).default([]),
  excerpt: z.string().default(''),
  document: z.string().nullable().default(null),
  href: z.string().nullable().default(null),
});

export const chatActivitySchema = z.object({
  id: z.string(),
  kind: z.enum(['thought', 'action']),
  label_code: z.string(),
  status: z.enum(['running', 'ok', 'warn', 'error']),
  latency_ms: z.number().optional(),
});

export const pendingActionSchema = z.object({
  id: z.string(),
  tool: z.string(),
  summary: z.string(),
  preview: z.record(z.string(), z.unknown()).default({}),
  run_id: z.string().nullable().default(null),
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
  run_id: z.string().nullable().default(null),
});

export const actionDecisionSchema = z.object({
  id: z.string(),
  status: z.string(),
  code: z.string().nullable().default(null),
  prompt_id: z.string().nullable().default(null),
  version_id: z.string().nullable().default(null),
  key_id: z.string().nullable().default(null),
  /** The minted key's plaintext, exactly once, on a confirmed create_api_key. */
  secret_once: z.string().nullable().default(null),
  directives: directiveListSchema.default([]),
  /** The automatic turn that picks the task back up. Absent when the decision closed it. */
  continuation: turnSchema.nullable().default(null),
});

export const feedbackSchema = z.object({
  message_id: z.string(),
  rating: z.enum(['helpful', 'not_helpful']),
  reason: z.enum(['incorrect', 'unsupported_source', 'misunderstood', 'other']).nullable().default(null),
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
  attachment_format: z.enum(['txt', 'md', 'markdown', 'json', 'yaml']).nullable().default(null),
  run_id: z.string().nullable().default(null),
});

export const transcriptSchema = z.object({
  conversation: conversationSchema,
  messages: z.array(messageSchema).default([]),
  pending: pendingActionSchema.nullable().default(null),
});

/**
 * The shape of the assistant, from `GET /api/v1/chat/pipeline`.
 *
 * A constant on the server, so it is fetched once and cached for the session.
 * It exists for one reason: a picture of only what ran cannot answer *why didn't
 * it search?*, and that is the question somebody opens the graph with.
 *
 * `agent` and `action` are the join back to a {@link TraceEntry}, and they are
 * not the same as `id`. The supervisor appears twice in one turn — once to route
 * and once to answer — so `agent` alone is ambiguous for exactly that node kind,
 * and `action` is what separates them. Everywhere else `action` is null and the
 * agent name is enough.
 */
export const pipelineNodeSchema = z.object({
  id: z.string(),
  agent: z.string(),
  action: z.string().nullable().default(null),
  kind: z.enum(['guardrail', 'supervisor', 'worker']),
  label_code: z.string(),
  /** Ordinal position, not a coordinate. Nodes sharing a stage are alternatives at one moment. */
  stage: z.number(),
  writes: z.boolean().default(false),
});

export const pipelineEdgeSchema = z.object({ source: z.string(), target: z.string() });

export const pipelineSchema = z.object({
  nodes: z.array(pipelineNodeSchema).default([]),
  edges: z.array(pipelineEdgeSchema).default([]),
});

export type PipelineNode = z.infer<typeof pipelineNodeSchema>;
export type PipelineEdge = z.infer<typeof pipelineEdgeSchema>;
export type Pipeline = z.infer<typeof pipelineSchema>;

/**
 * What one node did, in six values.
 *
 * The last two are the pair the flat trace list could never express, and they
 * are the reason the graph is worth drawing: `not-chosen` means the router
 * considered this tool and did not want it, `unreached` means the turn stopped
 * before this point and the question was never put. Same absence from the trace,
 * opposite meanings, and only one of them is ever a bug.
 */
export type NodeState = 'ok' | 'warn' | 'error' | 'refused' | 'not-chosen' | 'unreached';

export type TraceEntry = z.infer<typeof traceEntrySchema>;
export type Citation = z.infer<typeof citationSchema>;
export type ChatActivity = z.infer<typeof chatActivitySchema>;
export type PendingAction = z.infer<typeof pendingActionSchema>;
export type Turn = z.infer<typeof turnSchema>;
export type ActionDecision = z.infer<typeof actionDecisionSchema>;
export type Feedback = z.infer<typeof feedbackSchema>;
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
  activities?: ChatActivity[];
  streaming?: boolean;
  feedback?: 'helpful' | 'not_helpful';
  /** The format of the file this turn carried, when one did. */
  attachmentFormat?: AttachmentFormat | null;
  actionResult?: {
    promptId: string | null;
    versionId: string | null;
    keyId?: string | null;
    /** Shown once, with a copy affordance; never re-fetched anywhere. */
    secret?: string | null;
  };
}

/** The four formats the assistant will convert. `xml` is deliberately not one. */
export type AttachmentFormat = 'txt' | 'md' | 'markdown' | 'json' | 'yaml';
