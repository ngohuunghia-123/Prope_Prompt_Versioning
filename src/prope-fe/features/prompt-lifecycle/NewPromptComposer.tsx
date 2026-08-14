import { ArrowRight } from '@phosphor-icons/react';
import { FormProvider } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Notification } from '@/components/Notification';
import { ConvertToXmlDialog } from '@/features/prompt-lifecycle/components/ConvertToXmlDialog';
import { NewPromptAiPanel } from '@/features/prompt-lifecycle/components/NewPromptAiPanel';
import { NewPromptBodyPanel } from '@/features/prompt-lifecycle/components/NewPromptBodyPanel';
import { NewPromptMetadataPanel } from '@/features/prompt-lifecycle/components/NewPromptMetadataPanel';
import { SimilarPromptsDialog } from '@/features/prompt-lifecycle/components/SimilarPromptsDialog';
import type { PromptEditorValues } from '@/features/prompt-lifecycle/types';
import { useNewPromptComposer } from '@/features/prompt-lifecycle/useNewPromptComposer';

interface NewPromptComposerProps { initialValues: PromptEditorValues; }

export function NewPromptComposer({ initialValues }: NewPromptComposerProps) {
  const { t } = useTranslation();
  const composer = useNewPromptComposer(initialValues);
  const { importFlow } = composer;
  const busy = importFlow.stage === 'saving' || composer.form.formState.isSubmitting;

  return (
    <FormProvider {...composer.form}>
      <form className="mx-auto grid w-full max-w-(--container-content) gap-6 pb-20" onSubmit={(event) => { event.preventDefault(); void composer.evaluate(); }}>
        <NewPromptAiPanel
          pending={composer.suggestionMutation.isPending}
          error={composer.suggestionMutation.isError}
          applied={composer.suggestionMutation.isSuccess}
          onGenerate={composer.generateFromIdea}
        />
        {importFlow.importFailed ? (
          <Notification tone="error" title={t('lifecycle.states.error.title')}>{t('lifecycle.newPrompt.import.error')}</Notification>
        ) : null}
        {/* The duplicate check failing is not the import failing. Said here
            rather than in a dialog, because the flow has already carried on. */}
        {importFlow.similarityFailed ? (
          <Notification tone="info" title={t('lifecycle.newPrompt.similar.unavailableTitle')}>{t('lifecycle.newPrompt.similar.unavailable')}</Notification>
        ) : null}
        <div className="grid items-stretch gap-6 xl:grid-cols-[minmax(17rem,0.72fr)_minmax(0,1.7fr)]">
          <NewPromptMetadataPanel />
          <NewPromptBodyPanel />
        </div>
        <div className="flex justify-end sm:sticky sm:bottom-4 sm:z-20">
          <div className="rounded-full border border-border bg-canvas/95 p-1 shadow-floating backdrop-blur-sm">
            <Button type="submit" trailingIcon={<ArrowRight aria-hidden className="size-4" />} loading={busy}>
              {t(busy ? 'lifecycle.newPrompt.import.saving' : 'lifecycle.editor.evaluate')}
            </Button>
          </div>
        </div>
      </form>

      <SimilarPromptsDialog
        open={importFlow.stage === 'similar'}
        matches={importFlow.matches}
        onContinue={importFlow.chooseTarget}
        onStop={importFlow.cancel}
      />
      <ConvertToXmlDialog
        open={importFlow.stage === 'convert'}
        onConvert={() => importFlow.finish(true)}
        onKeepAsIs={() => importFlow.finish(false)}
        onCancel={importFlow.cancel}
      />
    </FormProvider>
  );
}
