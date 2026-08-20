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
