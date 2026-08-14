import type { CallRecord, RequestTrace } from '@/features/prompt-lifecycle/types';

export interface LogEntry {
  record: CallRecord;
  trace?: RequestTrace;
}
