export interface XmlBlock {
  id: string;
  tag: string;
  content: string;
}

export type XmlParseError = 'empty' | 'malformed' | 'topLevelText';
export type XmlParseResult = { success: true; blocks: XmlBlock[] } | { success: false; error: XmlParseError };

const createId = () => `xml_${crypto.randomUUID()}`;

export function parseXmlBlocks(xml: string): XmlParseResult {
  if (!xml.trim()) return { success: false, error: 'empty' };
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

export function serializeXmlBlocks(blocks: XmlBlock[]) {
  return blocks.map((block) => `<${block.tag}>\n${escapeXml(block.content.trim())}\n</${block.tag}>`).join('\n\n');
}

export function createXmlBlock(tag: string, content = ''): XmlBlock {
  return { id: createId(), tag, content };
}

export function extractTemplateTokens(content: string) {
  return Array.from(new Set(content.match(/{{\s*[^{}]+\s*}}/g) ?? []));
}
