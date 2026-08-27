import { parseXmlBlocks } from '@/features/prompt-lifecycle/xmlBlocks';

export type PromptBlockState = 'added' | 'changed' | 'unchanged' | 'removed';

export interface PromptBlockDiffItem {
  key: string;
  tag: string;
  before: string | null;
  after: string | null;
  state: PromptBlockState;
}

function indexedBlocks(body: string) {
  // No body, no blocks. The `raw` fallback below is for a body that exists and
  // will not parse; an ABSENT one is a different thing, and turning it into a
  // block was a lie with two visible consequences. The oldest revision has no
  // predecessor, so its detail page grew a phantom empty block tagged
  // "removed"; and in a comparison against a body that failed to load, the
  // fabricated `raw:0` matched none of the real keys, so every block came out
  // "added" and "only show changes" had nothing left to filter.
  if (!body.trim()) return [];
  const parsed = parseXmlBlocks(body);
  if (!parsed.success) return [{ key: 'raw:0', tag: 'raw', content: body }];
  const counts = new Map<string, number>();
  return parsed.blocks.map((block) => {
    const occurrence = counts.get(block.tag) ?? 0;
    counts.set(block.tag, occurrence + 1);
    return { key: `${block.tag}:${occurrence}`, tag: block.tag, content: block.content };
  });
}

export function diffPromptBlocks(beforeBody: string, afterBody: string): PromptBlockDiffItem[] {
  const before = indexedBlocks(beforeBody);
  const after = indexedBlocks(afterBody);
  const beforeByKey = new Map(before.map((block) => [block.key, block]));
  const afterByKey = new Map(after.map((block) => [block.key, block]));
  const keys = [...after.map((block) => block.key), ...before.filter((block) => !afterByKey.has(block.key)).map((block) => block.key)];
  return keys.map((key) => {
    const previous = beforeByKey.get(key);
    const current = afterByKey.get(key);
    const state: PromptBlockState = !previous ? 'added' : !current ? 'removed' : previous.content === current.content ? 'unchanged' : 'changed';
    return { key, tag: current?.tag ?? previous?.tag ?? 'raw', before: previous?.content ?? null, after: current?.content ?? null, state };
  });
}
