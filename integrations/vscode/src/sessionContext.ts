import type { z } from 'zod';
import type { sessionMessageSchema } from '@connector/sessionChatContracts';
import { ConnectorError } from './api';

type Message = z.infer<typeof sessionMessageSchema>;
type Passage = Message & { part: number; complete: boolean };
const budget = 32768;
const stopWords = new Set('the and for this that with from what how please cua cho cac mot nhung trong duoc hay toi ban nay voi session prompt'.split(' '));
const words = (text: string) => text.normalize('NFD').replace(/\p{M}/gu, '').replace(/đ/gi, 'd').toLowerCase().match(/[\p{L}\p{N}_-]{3,}/gu) ?? [];

function passages(messages: Message[]): Passage[] {
  return messages.flatMap((message) => {
    const whole: Passage = { ...message, part: 0, complete: true };
    if (JSON.stringify(whole).length <= budget - 128) return [whole];
    const parts: Passage[] = [];
    let start = 0;
    while (start < message.text.length) {
      let end = Math.min(start + 4000, message.text.length);
      if (end < message.text.length && /[\uD800-\uDBFF]/.test(message.text.charAt(end - 1))) end -= 1;
      parts.push({ ...message, text: message.text.slice(start, end), part: parts.length, complete: false });
      if (end === message.text.length) break;
      start = end - 200;
      if (/[\uDC00-\uDFFF]/.test(message.text.charAt(start))) start -= 1;
    }
    return parts;
  });
}

/** Local, deterministic retrieval. The native session stays in host memory. */
export function selectSessionContext(messages: Message[], question: string, previousQuestion = '') {
  if (!messages.length) throw new ConnectorError('session_context_empty');
  const candidates = passages(messages);
  const encode = (selected: Passage[], full = false) => JSON.stringify({
    scope: full ? 'full_session' : 'selected_passages', messages: selected,
  });
  const whole = encode(candidates, candidates.every((item) => item.complete));
  if (whole.length <= budget) return whole;

  const query = new Set(words(question).filter((term) => !stopWords.has(term)));
  const prior = new Set(words(previousQuestion).filter((term) => !stopWords.has(term) && !query.has(term)));
  const terms = [...query, ...prior];
  const counts = candidates.map((item) => {
    const frequencies = new Map<string, number>();
    for (const term of words(item.text)) if (query.has(term) || prior.has(term)) frequencies.set(term, (frequencies.get(term) ?? 0) + 1);
    return frequencies;
  });
  const frequency = new Map(terms.map((term) => [term, counts.filter((item) => item.has(term)).length]));
  const ranked = candidates.map((item, index) => ({ item, index, score: terms.reduce((score, term) => {
    const count = counts[index]?.get(term) ?? 0;
    return score + (count ? (query.has(term) ? 1 : 0.35) * Math.log(1 + candidates.length / (1 + (frequency.get(term) ?? 0))) * (1 + Math.log(count)) : 0);
  }, 0) })).sort((a, b) => b.score - a.score || b.index - a.index);
  const selected: typeof ranked = [];
  for (const candidate of ranked) {
    if (selected.length >= 48) break;
    const next = [...selected, candidate].sort((a, b) => a.index - b.index);
    if (encode(next.map((item) => item.item)).length <= budget) selected.push(candidate);
  }
  if (!selected.length) throw new ConnectorError('session_context_too_large', 413);
  return encode(selected.sort((a, b) => a.index - b.index).map((item) => item.item));
}
