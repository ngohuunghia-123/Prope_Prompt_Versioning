import { ArrowRight, ArrowsOut } from '@phosphor-icons/react';
import { useEffect, useRef } from 'react';
import { FormProvider } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { BottomActionDock } from '@/components/BottomActionDock';
import { Notification } from '@/components/Notification';
import { cn } from '@/lib/cn';
import { AgentStepBanner } from '@/features/prompt-lifecycle/components/AgentStepBanner';
import { ConvertToXmlDialog } from '@/features/prompt-lifecycle/components/ConvertToXmlDialog';
import { NewPromptImportPanel } from '@/features/prompt-lifecycle/components/NewPromptImportPanel';
import { NewPromptBodyPanel } from '@/features/prompt-lifecycle/components/NewPromptBodyPanel';
import { NewPromptMetadataPanel } from '@/features/prompt-lifecycle/components/NewPromptMetadataPanel';
import { RegistrationSteps } from '@/features/prompt-lifecycle/components/RegistrationSteps';
import { SimilarPromptsDialog } from '@/features/prompt-lifecycle/components/SimilarPromptsDialog';
import { SimilarityTraceSheet } from '@/features/prompt-lifecycle/components/SimilarityTraceSheet';
import type { PromptEditorValues } from '@/features/prompt-lifecycle/types';
import { useAgentImportSurface } from '@/features/prompt-lifecycle/useAgentImportSurface';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { useNewPromptComposer } from '@/features/prompt-lifecycle/useNewPromptComposer';

interface NewPromptComposerProps { initialValues: PromptEditorValues; mode?: 'create' | 'edit'; targetPromptId?: string; evaluationSearch?: string; }

/** What the one button at the bottom says, and what pressing it does. */
function submitLabelKey(stage: string, submitting: boolean): string {
  // `trace` is deliberately absent: like `similar` and `convert` it waits on a
  // person rather than on a request, and the button under the sheet should read
  // as the button they will come back to, not as work still running.
  if (stage === 'checking') return 'lifecycle.newPrompt.import.checking';
  if (stage === 'converting') return 'lifecycle.newPrompt.import.converting';
  if (stage === 'saving' || submitting) return 'lifecycle.newPrompt.import.saving';
  // A different label, because it is a different act. Closing the convert
  // dialog does NOT save — the blocks land in the editor and the flow waits
  // here so somebody can read them before they become a revision that cannot be
  // edited (A-021). Saying "Đánh giá" twice made the second press look like the
  // first one had failed rather than like the step it is.
  if (stage === 'review') return 'lifecycle.newPrompt.import.saveAndContinue';
  return 'lifecycle.editor.evaluate';
}

export function NewPromptComposer({ initialValues, mode = 'create', targetPromptId, evaluationSearch }: NewPromptComposerProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const format = useLocaleFormatters();
  const composer = useNewPromptComposer(initialValues, targetPromptId, evaluationSearch);
  const { importFlow, draft } = composer;
  const evaluationTarget = targetPromptId
    ? `/app/prompts/${targetPromptId}/evaluation/run${evaluationSearch ? `?${evaluationSearch}` : ''}`
    : undefined;
  const unchangedEdit = mode === 'edit' && !composer.form.formState.isDirty;
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

  // **A refused submit has to say something.** `handleSubmit` calls nothing when
  // the form is invalid, so any required field without a visible input — or with
  // an error nothing renders — turns the button into a no-op with no feedback at
  // all. Two such fields shipped that way. This is the backstop for the next
  // one: whatever is wrong, the screen now admits that something is.
  const invalid = composer.form.formState.isSubmitted && Object.keys(composer.form.formState.errors).length > 0;

  // The convert dialog closes over a long form, so the notice explaining that
  // nothing has been saved yet is usually off screen. Brought to the reader
  // rather than left for them to find.
  const reviewRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (importFlow.stage !== 'review') return;
    reviewRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [importFlow.stage]);

  return (
    <FormProvider {...composer.form}>
      <form
        className="mx-auto grid w-full max-w-(--container-content) gap-6 pb-24"
        onSubmit={(event) => {
          event.preventDefault();
          if (unchangedEdit && evaluationTarget) {
            void navigate(evaluationTarget);
            return;
          }
          void composer.evaluate();
        }}
      >
        {/* On both paths. Create has no destinations yet — evaluation needs a
            saved prompt id — so its second step is a label until saving gives
            it somewhere to go. */}
        <RegistrationSteps
          current="compose"
          targets={evaluationTarget ? { evaluate: evaluationTarget } : undefined}
        />
        <AgentStepBanner step={agent.step} />
        {/* Said out loud rather than restored silently: the composer opening
            with somebody else's half-finished prompt in it, three days later,
            is only reassuring if the screen admits that is what happened — and
            the way out has to be one press, not a field-by-field clear. */}
        {draft.restoredAt ? (
          <Notification tone="info" title={t('lifecycle.newPrompt.draft.restoredTitle')} onDismiss={draft.acknowledge}>
            <span>
              {t('lifecycle.newPrompt.draft.restored', { at: format.date(draft.restoredAt) })}{' '}
              <button type="button" className="cursor-pointer font-semibold text-link underline" onClick={draft.discard}>
                {t('lifecycle.newPrompt.draft.discard')}
              </button>
            </span>
          </Notification>
        ) : null}
        <NewPromptImportPanel onSubmitImport={() => void composer.evaluate()} />
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
        {invalid ? (
          <Notification tone="error" title={t('lifecycle.validation.blockedTitle')}>
            {t('lifecycle.validation.blockedBody')}
          </Notification>
        ) : null}
        {/* Both answers to the XML question land on `review`, so the notice has
            to read the answer. Announcing a conversion to somebody who chose
            "Giữ nguyên văn bản" describes work that did not happen, and the
            body below it is their own text — not blocks to check. */}
        {importFlow.stage === 'review' ? (
          <div ref={reviewRef}>
            <Notification
              tone="success"
              title={t(importFlow.converted ? 'lifecycle.newPrompt.review.title' : 'lifecycle.newPrompt.review.verbatimTitle')}
            >
              {t(importFlow.converted ? 'lifecycle.newPrompt.review.body' : 'lifecycle.newPrompt.review.verbatimBody')}
            </Notification>
          </div>
        ) : null}
        {/* The conversion is done and nothing has been written yet. Said out
            loud because the button changing its label is not enough of a signal
            that the screen is now waiting rather than working. */}
        <div className="grid items-start gap-6 xl:grid-cols-[minmax(17rem,0.72fr)_minmax(0,1.7fr)]">
          <NewPromptMetadataPanel editing={mode === 'edit'} />
          <NewPromptBodyPanel />
        </div>
        <BottomActionDock className={cn('transition-shadow', agent.highlight === 'import-summary' && 'ring-2 ring-inset ring-secondary')}>
          {/* The way back to the trace, and the reason it is here rather than
              inside the sheet: the sheet is closed. A run that has finished is
              the only evidence anybody has for "nothing over 90% matched", and
              once it is dismissed there was previously nothing on the screen
              that could bring it back. It re-reads what happened and starts
              nothing — pressing it again must not cost a second adjudication
              call. Absent until a run has something to show. */}
          {importFlow.steps.length > 0 && !importFlow.traceOpen ? (
            <Button
              type="button"
              intent="neutral"
              onClick={importFlow.reopenTrace}
              leadingIcon={<ArrowsOut aria-hidden className="size-4" />}
            >
              {t('lifecycle.similarity.trace.reopen')}
            </Button>
          ) : null}
          <Button type="submit" trailingIcon={<ArrowRight aria-hidden className="size-4" />} loading={busy}>
            {t(submitLabelKey(importFlow.stage, composer.form.formState.isSubmitting))}
          </Button>
        </BottomActionDock>
      </form>

      {/* Up from the press of the button and down when a dialog takes over, or
          when the person closes it. `trace` is the stage where it is the only
          thing on screen: the check found nothing over the floor, so there is
          nothing to ask and the trace is the whole answer. */}
      <SimilarityTraceSheet
        open={importFlow.traceOpen}
        running={importFlow.stage === 'checking'}
        steps={importFlow.steps}
        matchFloor={importFlow.matchFloor}
        belowFloor={importFlow.belowFloor}
        shown={importFlow.matches.length}
        failed={importFlow.similarityFailed}
        onClose={importFlow.dismissTrace}
      />
      <SimilarPromptsDialog
        open={importFlow.stage === 'similar'}
        matches={importFlow.matches}
        candidates={importFlow.candidates}
        coverage={importFlow.coverage}
        recommendedTarget={importFlow.recommendedTarget}
        retrieved={importFlow.retrieved}
        adjudicated={importFlow.adjudicated}
        matchFloor={importFlow.matchFloor}
        belowFloor={importFlow.belowFloor}
        sourceText={composer.form.watch('sourceText')}
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
