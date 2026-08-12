import type { PromptRevision } from '@/features/revisions/types';

export interface DiffLine { value: string; changed: boolean; }

export function useRevisionDiff(current: PromptRevision, earlier: PromptRevision) {
  const currentLines = current.content.split('\n');
  const earlierLines = earlier.content.split('\n');
  const length = Math.max(currentLines.length, earlierLines.length);
  const currentDiff: DiffLine[] = [];
  const earlierDiff: DiffLine[] = [];
  for (let index = 0; index < length; index += 1) {
    const currentValue = currentLines[index] ?? '';
    const earlierValue = earlierLines[index] ?? '';
    currentDiff.push({ value: currentValue, changed: currentValue !== earlierValue });
    earlierDiff.push({ value: earlierValue, changed: currentValue !== earlierValue });
  }
  return { currentDiff, earlierDiff };
}
