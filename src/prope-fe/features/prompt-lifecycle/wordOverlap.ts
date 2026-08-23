const WORD_PATTERN = /[\p{L}\p{N}_-]+/gu;

/** Words worth comparing: lowercased tokens, ignoring the trivially short. */
export function wordsOf(text: string): Set<string> {
  return new Set(text.toLocaleLowerCase().match(WORD_PATTERN)?.filter((word) => word.length > 2) ?? []);
}

/** Words both texts share — the set the heatmap highlights on either side. */
export function sharedWordsOf(a: string, b: string): Set<string> {
  const other = wordsOf(b);
  return new Set([...wordsOf(a)].filter((word) => other.has(word)));
}
