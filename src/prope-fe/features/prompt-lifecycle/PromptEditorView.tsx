import { FloppyDisk, Play } from '@phosphor-icons/react';
import { FormProvider, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Notification } from '@/components/Notification';
import { PromptEditorForm } from '@/features/prompt-lifecycle/components/PromptEditorForm';
import { PromptEditorSuggestions } from '@/features/prompt-lifecycle/components/PromptEditorSuggestions';
import { parseXmlBlocks, serializeXmlBlocks, type XmlBlock } from '@/features/prompt-lifecycle/xmlBlocks';
import { promptEditorSchema, type EditorSuggestion, type PromptEditorValues } from '@/features/prompt-lifecycle/types';

export interface PromptEditorViewProps {
  initialValues: PromptEditorValues;
  promptId: string;
  editing: boolean;
}

export function PromptEditorView({ initialValues, promptId, editing }: PromptEditorViewProps) {
  const { t } = useTranslation();
  const [applyToast, setApplyToast] = useState<string | null>(null);
  const [applyError, setApplyError] = useState<string | null>(null);
  const form = useForm<PromptEditorValues>({ resolver: zodResolver(promptEditorSchema), defaultValues: initialValues });

  const handleApply = (suggestion: EditorSuggestion): { ok: true } | { ok: false; reason: 'parse' } => {
    const promptBody = form.watch('promptBody');
    const parsed = parseXmlBlocks(promptBody);
    if (!parsed.success) {
      setApplyError(t('lifecycle.editor.suggestionApplyError'));
      setApplyToast(null);
      return { ok: false, reason: 'parse' };
    }
    const instructionsIndex = parsed.blocks.findIndex((block: XmlBlock) => block.tag === 'instructions');
    const instructionsBlock = parsed.blocks[instructionsIndex];
    const appendToInstructions = (block: XmlBlock) => ({
      ...block,
      content: block.content.trim().length > 0 ? `${block.content}\n${suggestion.body}` : suggestion.body,
    });
    const nextBlocks: XmlBlock[] = instructionsBlock
      ? parsed.blocks.map((block, index) => (index === instructionsIndex ? appendToInstructions(block) : block))
      : [...parsed.blocks, { id: `xml_${Date.now().toString(36)}`, tag: 'instructions', content: suggestion.body }];
    const serialized = serializeXmlBlocks(nextBlocks);
    form.setValue('promptBody', serialized, { shouldValidate: true, shouldDirty: true });
    setApplyError(null);
    setApplyToast(t('lifecycle.editor.suggestionApplied'));
    return { ok: true };
  };

  return (
    <FormProvider {...form}>
      <div className="grid gap-6">
        {applyToast ? <Notification tone="success" title={applyToast}>{t('lifecycle.editor.suggestionApplied')}</Notification> : null}
        {applyError ? <Notification tone="error" title={t('lifecycle.states.error.title')}>{applyError}</Notification> : null}
        <PromptEditorSuggestions onApply={handleApply} />
        <PromptEditorForm
          initialValues={initialValues}
          promptId={promptId}
          editing={editing}
          actionsSlot={({ onSave, onSaveAndGoToPlayground, saving }) => (
            <div className="flex flex-wrap justify-end gap-2 border-t border-border pt-6">
              <Button type="button" intent="neutral" leadingIcon={<FloppyDisk aria-hidden className="size-4" />} loading={saving} onClick={onSave}>{t('lifecycle.editor.saveDraft')}</Button>
              <Button type="button" intent="primary" leadingIcon={<Play aria-hidden className="size-4" />} onClick={onSaveAndGoToPlayground}>{t('lifecycle.editor.testChanges')}</Button>
            </div>
          )}
        />
      </div>
    </FormProvider>
  );
}
