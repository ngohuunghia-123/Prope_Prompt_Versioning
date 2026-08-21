import { z } from 'zod';

export const traceStatusSchema = z.enum(['success', 'error']);
export const observabilityRequestStatusSchema = z.enum(['available', 'disabled', 'forbidden', 'expired']);

export const traceMessageSchema = z.object({
  message_id: z.string(),
  role: z.enum(['system', 'user', 'assistant', 'tool']),
  content: z.string(),
  redacted: z.boolean(),
});

export const traceSpanSchema = z.object({
  span_id: z.string(),
  parent_span_id: z.string().nullable(),
  name: z.string(),
  kind: z.enum(['span', 'generation', 'event']),
  status: traceStatusSchema,
  duration_ms: z.number().int().nonnegative().nullable(),
  model: z.string().nullable().optional(),
  input_tokens: z.number().int().nullable().optional(),
  output_tokens: z.number().int().nullable().optional(),
  cost: z.union([z.string(), z.number()]).nullable().optional(),
  currency: z.string().nullable().optional(),
});

export const traceDetailSchema = z.object({
  trace_id: z.string(),
  status: traceStatusSchema,
  duration_ms: z.number().int().nonnegative().nullable(),
  spans: z.array(traceSpanSchema),
});

export const callObservabilitySchema = traceDetailSchema.extend({
  request: z.object({
    status: observabilityRequestStatusSchema,
    messages: z.array(traceMessageSchema),
  }),
});

export type TraceDetail = z.infer<typeof traceDetailSchema>;
export type CallObservability = z.infer<typeof callObservabilitySchema>;
export type TraceMessage = z.infer<typeof traceMessageSchema>;
