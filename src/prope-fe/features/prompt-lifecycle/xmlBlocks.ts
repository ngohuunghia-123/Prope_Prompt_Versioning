export interface XmlBlock {
  id: string;
  tag: string;
  content: string;
}

export type XmlParseError = 'empty' | 'malformed' | 'topLevelText';
export type XmlParseResult = { success: true; blocks: XmlBlock[] } | { success: false; error: XmlParseError };

const createId = () => `xml_${crypto.randomUUID()}`;

/** The nameless block's markers. `canonical_prompt.VERBATIM_OPEN` / `_CLOSE`. */
const VERBATIM_OPEN = '<>';
const VERBATIM_CLOSE = '</>';

/** The tag a nameless block carries in here: the empty string.
 *
 * Not a sentinel word like `'raw'`, because every renderer in this feature
 * prints a block as `<{tag}>` and the empty tag prints as `<>` — which is what
 * the body actually says. A sentinel would have needed each of them to learn a
 * special case. */
export const VERBATIM_TAG = '';

export function isVerbatimBlocks(blocks: XmlBlock[]): boolean {
  return blocks.length === 1 && blocks[0]?.tag === VERBATIM_TAG;
}

/** The text inside a nameless `<>` block, or `null` if this body is not one.
 *
 * The close is the LAST `</>`, matching `canonical_prompt.verbatim_text`. That
 * is what makes the round trip exact for every possible text, markers included,
 * which is the whole point of a form that promises not to touch anything.
 */
function verbatimText(xml: string): string | null {
  const body = xml.trim();
  if (body.length < VERBATIM_OPEN.length + VERBATIM_CLOSE.length) return null;
  if (!body.startsWith(VERBATIM_OPEN) || !body.endsWith(VERBATIM_CLOSE)) return null;
  // Exactly one newline off each end: the two the wrapper put there, and no
  // more. A prompt that opens on a blank line meant to.
  const inner = body.slice(VERBATIM_OPEN.length, -VERBATIM_CLOSE.length);
  return inner.replace(/^\n/, '').replace(/\n$/, '');
}

/**
 * This body as text to paste somewhere that is not Prope.
 *
 * A named block keeps its tag. `<role>` is not packaging around the prompt, it
 * is part of what the model reads, so a structured body is copied exactly as it
 * is stored — anything less would hand over a prompt that behaves differently.
 *
 * The nameless `<>` wrapper is the opposite: it is how Prope records *this text
 * was kept whole*, added by `serializeXmlBlocks` and never typed by anyone. The
 * screen already declines to print it as `<>`, and a person copying that prompt
 * wants the text they wrote, not the two markers that stored it.
 *
 * A body that parses as neither is returned unchanged. Copy is a read, and a
 * malformed body is still the one the revision holds.
 */
export function promptBodyForCopy(xml: string): string {
  return verbatimText(xml) ?? xml;
}

export function parseXmlBlocks(xml: string): XmlParseResult {
  if (!xml.trim()) return { success: false, error: 'empty' };
  // Checked before the parser, because `<>` is not well-formed XML and DOMParser
  // would call a perfectly valid body malformed.
  const verbatim = verbatimText(xml);
  if (verbatim !== null) {
    return verbatim.trim() ? { success: true, blocks: [{ id: createId(), tag: VERBATIM_TAG, content: verbatim }] } : { success: false, error: 'empty' };
  }
  const documentNode = new DOMParser().parseFromString(`<prope_root>${xml}</prope_root>`, 'application/xml');
  if (documentNode.querySelector('parsererror')) return { success: false, error: 'malformed' };
  const root = documentNode.documentElement;
  const hasTopLevelText = Array.from(root.childNodes).some((node) => node.nodeType === Node.TEXT_NODE && Boolean(node.textContent?.trim()));
  if (hasTopLevelText) return { success: false, error: 'topLevelText' };
  const blocks = Array.from(root.children).map((element) => ({ id: createId(), tag: element.tagName, content: element.textContent?.trim() ?? '' }));
  return blocks.length ? { success: true, blocks } : { success: false, error: 'empty' };
}

function escapeXml(value: string) {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
}

/** Blocks back to a body.
 *
 * A nameless block is written unescaped and alone: it means *this text was
 * stored whole*, and escaping it here would undo on save exactly what the
 * person chose when they declined the conversion. It is also the only block in
 * the body it appears in — `isVerbatimBlocks` is what the editor uses to keep
 * the add-block control off the screen, so no mixed set ever reaches here.
 */
export function serializeXmlBlocks(blocks: XmlBlock[]) {
  if (isVerbatimBlocks(blocks)) return `${VERBATIM_OPEN}\n${blocks[0]?.content ?? ''}\n${VERBATIM_CLOSE}`;
  return blocks.map((block) => `<${block.tag}>\n${escapeXml(block.content.trim())}\n</${block.tag}>`).join('\n\n');
}

export function createXmlBlock(tag: string, content = ''): XmlBlock {
  return { id: createId(), tag, content };
}

export function extractTemplateTokens(content: string) {
  return Array.from(new Set(content.match(/{{\s*[^{}]+\s*}}/g) ?? []));
}
