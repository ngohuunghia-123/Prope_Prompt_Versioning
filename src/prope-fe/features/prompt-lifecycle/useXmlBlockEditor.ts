import { useState } from 'react';
import { createXmlBlock, parseXmlBlocks, serializeXmlBlocks, type XmlBlock, type XmlParseError } from '@/features/prompt-lifecycle/xmlBlocks';

export type XmlEditorMode = 'blocks' | 'xml';

export function useXmlBlockEditor(value: string, onChange: (value: string) => void) {
  const initial = parseXmlBlocks(value);
  const [mode, setModeState] = useState<XmlEditorMode>('blocks');
  const [blocks, setBlocks] = useState<XmlBlock[]>(initial.success ? initial.blocks : []);
  const [rawXml, setRawXml] = useState(value);
  const [parseError, setParseError] = useState<XmlParseError | undefined>(initial.success ? undefined : initial.error);

  const commitBlocks = (next: XmlBlock[]) => {
    const serialized = serializeXmlBlocks(next);
    setBlocks(next);
    setRawXml(serialized);
    setParseError(next.length ? undefined : 'empty');
    onChange(serialized);
  };
  const setMode = (next: XmlEditorMode) => {
    if (next === 'blocks') {
      const parsed = parseXmlBlocks(rawXml);
      if (!parsed.success) { setParseError(parsed.error); return; }
      setBlocks(parsed.blocks);
      setParseError(undefined);
    }
    setModeState(next);
  };
  const updateRawXml = (next: string) => {
    setRawXml(next);
    onChange(next);
    const parsed = parseXmlBlocks(next);
    if (!parsed.success) { setParseError(parsed.error); return; }
    setBlocks(parsed.blocks);
    setParseError(undefined);
  };
  const updateBlock = (id: string, content: string) => commitBlocks(blocks.map((block) => block.id === id ? { ...block, content } : block));
  const addBlock = (tag: string) => commitBlocks([...blocks, createXmlBlock(tag)]);
  const removeBlock = (id: string) => commitBlocks(blocks.filter((block) => block.id !== id));
  const duplicateBlock = (id: string) => {
    const index = blocks.findIndex((block) => block.id === id);
    const source = blocks[index];
    if (!source) return;
    const next = [...blocks];
    next.splice(index + 1, 0, createXmlBlock(source.tag, source.content));
    commitBlocks(next);
  };
  const moveBlock = (id: string, direction: -1 | 1) => {
    const index = blocks.findIndex((block) => block.id === id);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= blocks.length) return;
    const next = [...blocks];
    [next[index], next[target]] = [next[target] as XmlBlock, next[index] as XmlBlock];
    commitBlocks(next);
  };
  return { mode, blocks, rawXml, parseError, setMode, updateRawXml, updateBlock, addBlock, removeBlock, duplicateBlock, moveBlock };
}
