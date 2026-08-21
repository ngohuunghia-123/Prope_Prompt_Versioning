import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { labelingRecordSchema, type CallLabel, type LabelingRecord } from '@/features/labeling/types';

const KEY = ['labeling', 'queue'] as const;
const STORAGE_KEY = 'prope-labeling-records';
const seed: LabelingRecord[] = [
  { callId: 'call_01JQ8AX1', promptId: 'prm_01M0BZ5JFMN742XS1BEXHARSYG', promptTitle: 'Untitled Prompt #1', revision: 'Version 4', app: 'Checkout assistant', outcome: 'ok', createdAt: '2026-08-20T09:12:00+07:00', requestBody: '{"messages":[{"role":"user","content":"Order [REDACTED_EMAIL] needs a refund"}]}', responseBody: 'I can help verify the refund policy and required order details.', label: null },
  { callId: 'call_01JQ8AX2', promptId: 'prm_01M0BZ5JFMN742XS1BEXHARSYG', promptTitle: 'Untitled Prompt #1', revision: 'Version 3', app: 'Support bot', outcome: 'fallback', createdAt: '2026-08-20T08:46:00+07:00', requestBody: '{"messages":[{"role":"user","content":"My phone is [REDACTED_PHONE]"}]}', responseBody: 'A support specialist will continue this request.', label: null },
];
const read = () => {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (!stored) return seed;
  try {
    const parsed = labelingRecordSchema.array().safeParse(JSON.parse(stored));
    return parsed.success ? parsed.data : seed;
  } catch {
    return seed;
  }
};
export const labelingQueueOptions = queryOptions({ queryKey: KEY, queryFn: async () => read() });
export function useSaveCallLabelMutation() {
  const client = useQueryClient();
  return useMutation({ mutationFn: async ({ callId, label }: { callId: string; label: CallLabel }) => { const next = read().map((record) => record.callId === callId ? { ...record, label } : record); localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); return next; }, onSuccess: (next) => client.setQueryData(KEY, next) });
}
