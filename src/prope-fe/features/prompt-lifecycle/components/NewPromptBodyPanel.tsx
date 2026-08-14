import { Controller, useFormContext } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs';
import { PromptSourcePanel } from '@/features/prompt-lifecycle/components/PromptSourcePanel';
import { XmlBlockEditor } from '@/features/prompt-lifecycle/components/XmlBlockEditor';
import type { PromptEditorValues } from '@/features/prompt-lifecycle/types';

/** Two ways in: bring a prompt you already have, or write a new one here.
 *
 * The selected tab is `sourceMode` on the form rather than local state, because
 * it decides which field the schema validates and which text the import flow
 * reads. Holding it twice would let the visible tab and the validated field
 * disagree — which is a submit that fails against a rule the screen is not
 * showing.
 */
export function NewPromptBodyPanel() {
  const { t } = useTranslation();
  const form = useFormContext<PromptEditorValues>();
  const sourceMode = form.watch('sourceMode');

  return (
    <Card title={t('lifecycle.newPrompt.promptBody')} description={t('lifecycle.editor.promptBodyHint')} className="min-h-full">
      <Tabs
        value={sourceMode}
        onValueChange={(value) => form.setValue('sourceMode', value as PromptEditorValues['sourceMode'], { shouldValidate: true })}
      >
        <TabsList className="self-start">
          <TabsTrigger value="existing">{t('lifecycle.newPrompt.source.tabExisting')}</TabsTrigger>
          <TabsTrigger value="authored">{t('lifecycle.newPrompt.source.tabAuthored')}</TabsTrigger>
        </TabsList>

        <TabsContent value="existing">
          <PromptSourcePanel />
        </TabsContent>

        <TabsContent value="authored">
          <Controller
            name="promptBody"
            control={form.control}
            render={({ field, fieldState }) => (
              <XmlBlockEditor value={field.value} onChange={field.onChange} error={fieldState.error ? t('lifecycle.xml.errors.malformed') : undefined} />
            )}
          />
        </TabsContent>
      </Tabs>
    </Card>
  );
}
