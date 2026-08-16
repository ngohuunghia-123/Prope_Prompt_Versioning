import { ArrowRight } from '@phosphor-icons/react';
import { FormProvider } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { BottomActionDock } from '@/components/BottomActionDock';
import { Notification } from '@/components/Notification';
import { cn } from '@/lib/cn';
import { AgentStepBanner } from '@/features/prompt-lifecycle/components/AgentStepBanner';
import { ConvertToXmlDialog } from '@/features/prompt-lifecycle/components/ConvertToXmlDialog';
import { NewPromptImportPanel } from '@/features/prompt-lifecycle/components/NewPromptImportPanel';
import { NewPromptBodyPanel } from '@/features/prompt-lifecycle/components/NewPromptBodyPanel';
import { NewPromptMetadataPanel } from '@/features/prompt-lifecycle/components/NewPromptMetadataPanel';
import { SimilarPromptsDialog } from '@/features/prompt-lifecycle/components/SimilarPromptsDialog';
import type { PromptEditorValues } from '@/features/prompt-lifecycle/types';
import { useAgentImportSurface } from '@/features/prompt-lifecycle/useAgentImportSurface';
import { useNewPromptComposer } from '@/features/prompt-lifecycle/useNewPromptComposer';

interface NewPromptComposerProps { initialValues: PromptEditorValues; }

/** What the one button at the bottom says, and what pressing it does. */
function submitLabelKey(stage: string, submitting: boolean): string {
  if (stage === 'checking') return 'lifecycle.newPrompt.import.checking';
  if (stage === 'converting') return 'lifecycle.newPrompt.import.converting';
  if (stage === 'review') return 'lifecycle.newPrompt.import.continue';
  if (stage === 'saving' || submitting) return 'lifecycle.newPrompt.import.saving';
  return 'lifecycle.editor.evaluate';
}

export function NewPromptComposer({ initialValues }: NewPromptComposerProps) {
  const { t } = useTranslation();
  const composer = useNewPromptComposer(initialValues);
  const { importFlow } = composer;
  // Everything the agent asked this screen to do arrives here: a body it already
  // converted, the step it thinks the flow is on, and what to point at.
  const agent = useAgentImportSurface(composer.form);
  // `checking`, `converting` and `saving` are the stages with a request in
  // flight and no dialog on screen — exactly the window in which a second press
  // would start a second import. `similar` and `convert` are waiting on the
  // person, and the form behind them is meant to stay readable. `review` is
  // waiting on the person too, but the form is theirs to edit and the button is
  // how they leave it.
  const busy =
    importFlow.stage === 'checking' ||
    importFlow.stage === 'converting' ||
    importFlow.stage === 'saving' ||
    composer.form.formState.isSubmitting;

  const reviewing = importFlow.stage === 'review';

  return (
    <FormProvider {...composer.form}>
      <form
        className="mx-auto grid w-full max-w-(--container-content) gap-6 pb-24"
        onSubmit={(event) => {
          event.preventDefault();
          if (reviewing) { void composer.confirmReview(); return; }
          void composer.evaluate();
        }}
      >
        <AgentStepBanner step={agent.step} />
        <NewPromptImportPanel />
        {importFlow.importFailed ? (
          <Notification tone="error" title={t('lifecycle.states.error.title')}>{t('lifecycle.newPrompt.import.error')}</Notification>
        ) : null}
        {/* Conversion failing is not the save failing, and it leaves the source
            exactly where it was — so the answer is to press the button again. */}
        {importFlow.conversionFailed ? (
          <Notification tone="error" title={t('lifecycle.states.error.title')}>{t('lifecycle.newPrompt.import.conversionError')}</Notification>
        ) : null}
        {/* The duplicate check failing is not the import failing. Said here
            rather than in a dialog, because the flow has already carried on. */}
        {importFlow.similarityFailed ? (
          <Notification tone="info" title={t('lifecycle.newPrompt.similar.unavailableTitle')}>{t('lifecycle.newPrompt.similar.unavailable')}</Notification>
        ) : null}
        {/* The conversion is done and nothing has been written yet. Said out
            loud because the button changing its label is not enough of a signal
            that the screen is now waiting rather than working. */}
        {reviewing ? (
          <Notification tone="info" title={t('lifecycle.newPrompt.review.title')}>{t('lifecycle.newPrompt.review.body')}</Notification>
        ) : null}
        <div className="grid items-start gap-6 xl:grid-cols-[minmax(17rem,0.72fr)_minmax(0,1.7fr)]">
          <NewPromptMetadataPanel />
          <NewPromptBodyPanel />
        </div>
        <BottomActionDock className={cn('transition-shadow', agent.highlight === 'import-summary' && 'ring-2 ring-inset ring-secondary')}>
          <Button type="submit" trailingIcon={<ArrowRight aria-hidden className="size-4" />} loading={busy}>
            {t(submitLabelKey(importFlow.stage, composer.form.formState.isSubmitting))}
          </Button>
        </BottomActionDock>
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
