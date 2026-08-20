import { z } from 'zod';

export const traceSubjectSchema = z.enum(['call', 'evaluation']);
export const traceStatusSchema = z.enum(['success', 'error']);

export const traceMessageSchema = z.object({
  message_id: z.string(),
  role: z.enum(['system', 'user', 'assistant', 'tool']),
  content: z.string(),
  redacted: z.boolean().default(false),
});

export const traceSpanSchema = z.object({
  span_id: z.string(),
  parent_span_id: z.string().nullable().default(null),
  name: z.string(),
  kind: z.enum(['span', 'generation']),
  status: traceStatusSchema,
  start_offset_ms: z.number().int().nonnegative(),
  duration_ms: z.number().int().nonnegative(),
  model: z.string().nullable().default(null),
  input_tokens: z.number().int().nullable().default(null),
  output_tokens: z.number().int().nullable().default(null),
});

export const traceDetailSchema = z.object({
  trace_id: z.string(),
  subject: traceSubjectSchema,
  provider: z.literal('langfuse'),
  status: traceStatusSchema,
  duration_ms: z.number().int().nonnegative(),
  observed_at: z.string(),
  messages: z.array(traceMessageSchema),
  spans: z.array(traceSpanSchema),
});

export type TraceSubject = z.infer<typeof traceSubjectSchema>;
export type TraceDetail = z.infer<typeof traceDetailSchema>;
export type TraceMessage = z.infer<typeof traceMessageSchema>;
export type TraceSpan = z.infer<typeof traceSpanSchema>;
