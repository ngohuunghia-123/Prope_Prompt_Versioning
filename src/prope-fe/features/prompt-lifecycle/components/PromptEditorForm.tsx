import { ArrowLeft, ArrowRight, CaretDown, CaretUp, Check } from '@phosphor-icons/react';
import { zodResolver } from '@hookform/resolvers/zod';
import { Controller, FormProvider, useForm } from 'react-hook-form';
import { useQuery } from '@tanstack/react-query';
import { type ReactNode, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/Card';
import { Notification } from '@/components/Notification';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { PromptTestPanel } from '@/features/prompt-lifecycle/components/PromptTestPanel';
import { WizardQuestionStep } from '@/features/prompt-lifecycle/components/WizardQuestionStep';
import { WizardSuggestions } from '@/features/prompt-lifecycle/components/WizardSuggestions';
import { ProviderBindingFields } from '@/features/prompt-lifecycle/components/ProviderBindingFields';
import { XmlBlockEditor } from '@/features/prompt-lifecycle/components/XmlBlockEditor';
import { useSavePromptMutation, useStartEvaluationMutation, useWizardSuggestionMutation, wizardStepsOptions } from '@/features/prompt-lifecycle/queries';
import { promptEditorSchema, wizardAnswersSchema, type PromptEditorValues, type PromptSuggestion, type WizardAnswers, type WizardStep } from '@/features/prompt-lifecycle/types';
import { extractTemplateTokens, parseXmlBlocks } from '@/features/prompt-lifecycle/xmlBlocks';

export interface PromptEditorFormActionsSlotProps {
  onSave: () => void;
  onSaveAndGoToPlayground: () => void;
  saving: boolean;
}

export interface PromptEditorFormProps {
  initialValues: PromptEditorValues;
  promptId: string;
  editing?: boolean;
  wizardSuggestion?: PromptSuggestion;
  actionsSlot?: (props: PromptEditorFormActionsSlotProps) => ReactNode;
}

const wizardDefaultAnswers: WizardAnswers = { intent: '', context: '', constraints: [], model: '' };

export function PromptEditorForm({ initialValues, promptId, editing = false, actionsSlot }: PromptEditorFormProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [contentExpanded, setContentExpanded] = useState(true);
  const [showWizard, setShowWizard] = useState(true);
  const [wizardStep, setWizardStep] = useState(0);
  const [selectedSuggestion, setSelectedSuggestion] = useState<PromptSuggestion | null>(null);
  const saveMutation = useSavePromptMutation();
  const evaluationMutation = useStartEvaluationMutation(promptId);
  const form = useForm<PromptEditorValues>({ resolver: zodResolver(promptEditorSchema), defaultValues: initialValues });
  const wizardForm = useForm<WizardAnswers>({ defaultValues: wizardDefaultAnswers, mode: 'onChange' });

  const stepsQuery = useQuery(wizardStepsOptions);
  const suggestionMutation = useWizardSuggestionMutation();
  const steps = stepsQuery.data ?? [];
  const isSuggestionStep = wizardStep === steps.length;
  const totalSteps = steps.length + 1;
  const currentStepData = steps[wizardStep] as WizardStep | undefined;
  const currentValue = currentStepData ? wizardForm.watch(currentStepData.id) : undefined;
  const fieldError = currentStepData ? (wizardForm.formState.errors[currentStepData.id]?.message as string | undefined) : undefined;
  const hasCurrentAnswer = Array.isArray(currentValue) ? currentValue.length > 0 : Boolean(typeof currentValue === 'string' ? currentValue.trim() : undefined);

  const applySuggestion = (suggestion: PromptSuggestion) => {
    form.setValue('title', suggestion.title, { shouldDirty: true });
    // The model name is deliberately not touched. This screen only ever revises
    // an existing prompt, whose namespace and name are immutable (A-021).
    form.setValue('promptBody', suggestion.promptBody, { shouldDirty: true });
    setShowWizard(false);
  };

  const confirmWizardSuggestion = () => {
    if (!selectedSuggestion) return;
    applySuggestion(selectedSuggestion);
  };

  const generateWizardSuggestions = () => {
    const parsed = wizardAnswersSchema.safeParse(wizardForm.getValues());
    if (!parsed.success) return;
    setSelectedSuggestion(null);
    suggestionMutation.mutate(parsed.data);
  };

  const goWizardNext = async () => {
    if (!currentStepData || !(await wizardForm.trigger(currentStepData.id))) return;
    if (wizardStep === steps.length - 1) {
      setWizardStep(steps.length);
      generateWizardSuggestions();
      return;
    }
    setWizardStep((step) => step + 1);
  };

  const fieldError2 = (name: keyof PromptEditorValues) => form.formState.errors[name] ? t('lifecycle.validation.required') : undefined;

  const handleSave = form.handleSubmit((values) => saveMutation.mutate(values, { onSuccess: () => void navigate(`/app/prompts/${promptId}`) }));

  const handleSaveAndGoToPlayground = form.handleSubmit((values) => {
    saveMutation.mutate(values, { onSuccess: () => void navigate(`/app/prompts/${promptId}/playground`) });
  });

  const handleEvaluate = form.handleSubmit((values) => evaluationMutation.mutate(values, { onSuccess: () => void navigate(`/app/prompts/${promptId}`) }));

  const pending = saveMutation.isPending || evaluationMutation.isPending;
  const accessOptions = [{ value: 'private', label: t('lifecycle.access.private') }, { value: 'workspace', label: t('lifecycle.access.workspace') }];
  const promptBody = form.watch('promptBody');
  const parsed = parseXmlBlocks(promptBody);
  const blocks = parsed.success ? parsed.blocks.length : 0;
  const templateVariables = extractTemplateTokens(promptBody).map((token) => token.slice(2, -2).trim());
  const variables = templateVariables.length;

  const defaultActions = (
    <div className="flex flex-wrap justify-end gap-2">
      <Button type="button" intent="ghost" disabled={pending} loading={saveMutation.isPending} onClick={() => void handleSave()}>
        {t('lifecycle.editor.saveDraft')}
      </Button>
      <Button type="button" disabled={pending} loading={evaluationMutation.isPending} onClick={() => void handleEvaluate()}>
        {t(evaluationMutation.isPending ? 'lifecycle.editor.startingEvaluation' : 'lifecycle.editor.evaluate')}
      </Button>
    </div>
  );

  const wizardSlot = (() => {
    if (!editing && showWizard) {
      if (stepsQuery.isPending) return <p role="status" className="py-12 text-center text-body text-muted">{t('lifecycle.wizard.loading')}</p>;
      if (stepsQuery.isError) return <p role="alert" className="py-12 text-center text-body text-danger-text">{t('lifecycle.wizard.loadError')}</p>;
      return (
        <div className="space-y-6">
          <div className="mb-8">
            <div className="flex items-center justify-between text-caption text-muted">
              <span>{t('lifecycle.wizard.stepProgress', { current: wizardStep + 1, total: totalSteps })}</span>
              <span>{Math.round(((wizardStep + 1) / totalSteps) * 100)}%</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-subtle">
              <div className="h-full rounded-full bg-primary transition-all duration-300" style={{ width: `${((wizardStep + 1) / totalSteps) * 100}%` }} />
            </div>
          </div>
          <div className="mb-8 min-h-60">
            {isSuggestionStep ? (
              <WizardSuggestions
                suggestions={suggestionMutation.data}
                selectedId={selectedSuggestion?.id}
                pending={suggestionMutation.isPending}
                error={suggestionMutation.isError}
                onRetry={generateWizardSuggestions}
                onSelect={setSelectedSuggestion}
              />
            ) : currentStepData ? (
              <WizardQuestionStep
                step={currentStepData}
                value={currentValue}
                error={fieldError}
                onChange={(value) => wizardForm.setValue(currentStepData.id, value as never, { shouldDirty: true, shouldValidate: true })}
              />
            ) : null}
          </div>
          <div className="flex items-center justify-between border-t border-border pt-6">
            <div>{wizardStep > 0 ? <Button intent="ghost" leadingIcon={<ArrowLeft aria-hidden className="size-4" />} onClick={() => setWizardStep((step) => step - 1)}>{t('lifecycle.wizard.back')}</Button> : null}</div>
            <div className="flex gap-3">
              <Button intent="ghost" onClick={() => setShowWizard(false)}>{t('lifecycle.wizard.cancel')}</Button>
              {isSuggestionStep ? (
                <Button disabled={!selectedSuggestion} onClick={confirmWizardSuggestion} leadingIcon={<Check aria-hidden className="size-4" weight="bold" />}>
                  {t('lifecycle.wizard.confirmAndEdit')}
                </Button>
              ) : (
                <Button disabled={!hasCurrentAnswer} onClick={() => void goWizardNext()} trailingIcon={<ArrowRight aria-hidden className="size-4" />}>
                  {wizardStep === steps.length - 1 ? t('lifecycle.wizard.generate') : t('lifecycle.wizard.next')}
                </Button>
              )}
            </div>
          </div>
        </div>
      );
    }
    return null;
  })();

  const headerWizard = !editing && showWizard ? wizardSlot : undefined;

  return (
    <FormProvider {...form} {...wizardForm}>
      <form className="grid gap-6 pb-16 xl:pb-0" onSubmit={(event) => { event.preventDefault(); void handleEvaluate(); }}>
        <PageIntro
          wizard={headerWizard}
          action={actionsSlot ? actionsSlot({ onSave: handleSave, onSaveAndGoToPlayground: handleSaveAndGoToPlayground, saving: pending }) : defaultActions}
        />
      {saveMutation.isError || evaluationMutation.isError ? (
        <Notification tone="error" title={t('lifecycle.states.error.title')}>
          {t(evaluationMutation.isError ? 'lifecycle.editor.evaluationError' : 'lifecycle.editor.saveError')}
        </Notification>
      ) : null}
      <div className="grid gap-6 xl:grid-cols-3">
        <div className="grid content-start gap-6 xl:col-span-2">
          <Card title={t('lifecycle.editor.promptMetadata')}>
            <div className="grid gap-5 sm:grid-cols-2">
              <Input label={t('lifecycle.editor.title')} error={fieldError2('title')} {...form.register('title')} />
              {/* Shown, never edited. This screen adds a revision to a prompt
                  that already exists, and A-021 fixed its model name when it was
                  created — an editable field here could only ever produce a save
                  the server refuses. */}
              <Input label={t('lifecycle.editor.modelName')} hint={t('lifecycle.editor.modelNameLocked')} disabled value={`${form.watch('namespace')}/${form.watch('name')}`} readOnly />
              <Controller name="access" control={form.control} render={({ field }) => <Select label={t('lifecycle.editor.access')} options={accessOptions} value={field.value} onValueChange={field.onChange} />} />
              <ProviderBindingFields />
            </div>
          </Card>
          <Card title={undefined}>
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-display text-heading-3 text-ink">{t('lifecycle.editor.promptDetails')}</h2>
              <button type="button" onClick={() => setContentExpanded((value) => !value)} aria-expanded={contentExpanded} className="flex cursor-pointer items-center gap-2 text-caption font-medium text-link focus-visible:outline-2 focus-visible:outline-focus">
                {contentExpanded ? <CaretUp aria-hidden className="size-5" /> : <CaretDown aria-hidden className="size-5" />}
                {contentExpanded ? t('lifecycle.editor.collapse') : t('lifecycle.editor.expand')}
              </button>
            </div>
            {!contentExpanded ? (
              <p className="text-caption text-muted">{t('lifecycle.editor.collapsedSummary', { blocks, variables })}</p>
            ) : (
              <div className="grid gap-6">
                <Controller name="promptBody" control={form.control} render={({ field, fieldState }) => <XmlBlockEditor value={field.value} onChange={field.onChange} error={fieldState.error ? t('lifecycle.xml.errors.malformed') : undefined} />} />
                <div className="grid gap-5">
                  <Textarea label={t('lifecycle.editor.fallbackAnswer')} error={fieldError2('fallbackAnswer')} {...form.register('fallbackAnswer')} />
                  <Textarea className="min-h-24" label={t('lifecycle.editor.changeSummary')} error={fieldError2('changeSummary')} {...form.register('changeSummary')} />
                </div>
              </div>
            )}
          </Card>
        </div>
        <PromptTestPanel variables={templateVariables} />
      </div>
    </form>
    </FormProvider>
  );
}
