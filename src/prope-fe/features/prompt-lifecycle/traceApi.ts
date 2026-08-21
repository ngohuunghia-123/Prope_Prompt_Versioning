import {
  traceDetailSchema,
  type TraceDetail,
  type TraceSubject,
} from '@/features/prompt-lifecycle/traceTypes';

interface TraceDetailInput {
  subjectId: string;
  subject: TraceSubject;
  failed?: boolean;
  model?: string | null;
}

/**
 * Query-layer placeholder for the Langfuse trace adapter.
 *
 * The UI consumes a provider-neutral shape. Replacing this fixture with the
 * server-side Langfuse adapter therefore does not change the drawer or eval
 * surfaces, and Langfuse credentials never need to reach the browser.
 */
export async function getTraceDetail(input: TraceDetailInput): Promise<TraceDetail> {
  const totalDuration = input.failed ? 842 : 7_820;
  const providerDuration = input.failed ? 610 : 7_483;
  const traceId = `lf_${input.subjectId}`;

  return traceDetailSchema.parse({
    trace_id: traceId,
    subject: input.subject,
    provider: 'langfuse',
    status: input.failed ? 'error' : 'success',
    duration_ms: totalDuration,
    observed_at: new Date().toISOString(),
    messages: input.subject === 'evaluation'
      ? [
          { message_id: `${traceId}_user`, role: 'user', content: 'Lời chào', redacted: false },
          {
            message_id: `${traceId}_assistant`,
            role: 'assistant',
            content: input.failed ? '[dispatch_failed]' : 'Xin chào! Tôi có thể giúp gì cho bạn?',
            redacted: false,
          },
        ]
      : [
          {
            message_id: `${traceId}_system`,
            role: 'system',
            content: '[Nội dung system prompt đã được redact]',
            redacted: true,
          },
          {
            message_id: `${traceId}_user`,
            role: 'user',
            content: 'Tôi cần hỗ trợ với yêu cầu này.',
            redacted: false,
          },
          {
            message_id: `${traceId}_assistant`,
            role: 'assistant',
            content: input.failed
              ? '[Không có phản hồi do provider error]'
              : 'Tôi đã kiểm tra ngữ cảnh và đây là kết quả.',
            redacted: input.failed,
          },
        ],
    spans: [
      {
        span_id: `${traceId}_root`,
        parent_span_id: null,
        name: 'gateway.request',
        kind: 'span',
        status: input.failed ? 'error' : 'success',
        start_offset_ms: 0,
        duration_ms: totalDuration,
      },
      {
        span_id: `${traceId}_resolve`,
        parent_span_id: `${traceId}_root`,
        name: 'prompt.resolve_revision',
        kind: 'span',
        status: 'success',
        start_offset_ms: 18,
        duration_ms: 41,
      },
      {
        span_id: `${traceId}_generation`,
        parent_span_id: `${traceId}_root`,
        name: input.subject === 'evaluation' ? 'evaluation.dispatch' : 'provider.generation',
        kind: 'generation',
        status: input.failed ? 'error' : 'success',
        start_offset_ms: 93,
        duration_ms: providerDuration,
        model: input.model ?? 'claude-haiku-4-5-20251001',
        input_tokens: input.failed ? null : 832,
        output_tokens: input.failed ? null : 558,
      },
      {
        span_id: `${traceId}_ledger`,
        parent_span_id: `${traceId}_root`,
        name: 'ledger.record_call',
        kind: 'span',
        status: 'success',
        start_offset_ms: Math.max(totalDuration - 44, 0),
        duration_ms: 27,
      },
    ],
  });
}
