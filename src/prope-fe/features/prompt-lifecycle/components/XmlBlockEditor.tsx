import { Plus } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SegmentedControl } from '@/components/SegmentedControl';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { XmlBlockCard } from '@/features/prompt-lifecycle/components/XmlBlockCard';
import { useXmlBlockEditor, type XmlEditorMode } from '@/features/prompt-lifecycle/useXmlBlockEditor';

export interface XmlBlockEditorProps {
  value: string;
  onChange: (value: string) => void;
  error?: string;
}

const blockTypes = ['system', 'context', 'instructions', 'output_format', 'examples', 'constraints'];

export function XmlBlockEditor({ value, onChange, error }: XmlBlockEditorProps) {
  const { t } = useTranslation();
  const editor = useXmlBlockEditor(value, onChange);
  const [blockType, setBlockType] = useState(blockTypes[2] ?? 'instructions');
  const parseError = editor.parseError ? t(`lifecycle.xml.errors.${editor.parseError}`) : undefined;
  const modeOptions = [{ value: 'blocks', label: t('lifecycle.xml.blocks') }, { value: 'xml', label: t('lifecycle.xml.xml') }];
  const typeOptions = blockTypes.map((tag) => ({ value: tag, label: `<${tag}>` }));
  return (
    <section aria-labelledby="xml-editor-title" className="grid gap-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div><h3 id="xml-editor-title" className="text-body font-semibold text-ink">{t('lifecycle.editor.promptBody')}</h3><p className="mt-1 text-caption text-muted">{t('lifecycle.xml.description')}</p></div>
        <SegmentedControl className="sm:max-w-64" label={t('lifecycle.xml.mode')} name="xml-editor-mode" options={modeOptions} value={editor.mode} onValueChange={(next) => editor.setMode(next as XmlEditorMode)} />
      </div>
      {editor.mode === 'blocks' ? (
        <>
          <ol className="grid gap-4">{editor.blocks.map((block, index) => <li key={block.id}><XmlBlockCard block={block} first={index === 0} last={index === editor.blocks.length - 1} onChange={(content) => editor.updateBlock(block.id, content)} onMove={(direction) => editor.moveBlock(block.id, direction)} onDuplicate={() => editor.duplicateBlock(block.id)} onRemove={() => editor.removeBlock(block.id)} /></li>)}</ol>
          <div className="flex flex-col gap-3 rounded-xl border border-dashed border-border p-4 sm:flex-row sm:items-end">
            <div className="min-w-0 flex-1"><Select label={t('lifecycle.xml.newBlockType')} options={typeOptions} value={blockType} onValueChange={setBlockType} /></div>
            <Button type="button" intent="neutral" leadingIcon={<Plus aria-hidden />} onClick={() => editor.addBlock(blockType)}>{t('lifecycle.xml.addBlock')}</Button>
          </div>
        </>
      ) : <Textarea className="min-h-96 font-mono" label={t('lifecycle.xml.rawLabel')} value={editor.rawXml} error={parseError ?? error} onChange={(event) => editor.updateRawXml(event.target.value)} spellCheck={false} />}
      {editor.mode === 'blocks' && (parseError || error) ? <p role="alert" className="text-caption text-danger-text">{parseError ?? error}</p> : null}
    </section>
  );
}
