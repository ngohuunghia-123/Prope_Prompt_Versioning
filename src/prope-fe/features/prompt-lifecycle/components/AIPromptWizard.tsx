import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowLeft, ArrowRight, Check } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { WizardQuestionStep } from '@/features/prompt-lifecycle/components/WizardQuestionStep';
import { WizardSuggestions } from '@/features/prompt-lifecycle/components/WizardSuggestions';
import { useWizardSuggestionMutation, wizardStepsOptions } from '@/features/prompt-lifecycle/queries';
import { wizardAnswersSchema, type PromptSuggestion, type WizardAnswers } from '@/features/prompt-lifecycle/types';

interface AIPromptWizardProps {
  onComplete?: (suggestion: PromptSuggestion) => void;
  onCancel?: () => void;
}

const defaultAnswers: WizardAnswers = { intent: '', context: '', constraints: [], model: '' };

export function AIPromptWizard({ onComplete, onCancel }: AIPromptWizardProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(0);
  const [selectedSuggestion, setSelectedSuggestion] = useState<PromptSuggestion>();
  const stepsQuery = useQuery(wizardStepsOptions);
  const suggestionMutation = useWizardSuggestionMutation();
  const form = useForm<WizardAnswers>({ resolver: zodResolver(wizardAnswersSchema), defaultValues: defaultAnswers, mode: 'onChange' });

  if (stepsQuery.isPending) return <p role="status" className="py-12 text-center text-body text-muted">{t('lifecycle.wizard.loading')}</p>;
  if (stepsQuery.isError) return <p role="alert" className="py-12 text-center text-body text-danger-text">{t('lifecycle.wizard.loadError')}</p>;

  const steps = stepsQuery.data;
  const currentStepData = steps[currentStep];
  const isSuggestionStep = currentStep === steps.length;
  const totalSteps = steps.length + 1;
  const currentValue = currentStepData ? form.watch(currentStepData.id) : undefined;
  const fieldError = currentStepData ? form.formState.errors[currentStepData.id]?.message : undefined;
  const hasCurrentAnswer = Array.isArray(currentValue) ? currentValue.length > 0 : Boolean(currentValue?.trim());

  const generateSuggestions = () => {
    const parsed = wizardAnswersSchema.safeParse(form.getValues());
    if (!parsed.success) return;
    setSelectedSuggestion(undefined);
    suggestionMutation.mutate(parsed.data);
  };

  const goNext = async () => {
    if (!currentStepData || !(await form.trigger(currentStepData.id))) return;
    if (currentStep === steps.length - 1) {
      setCurrentStep(steps.length);
      generateSuggestions();
      return;
    }
    setCurrentStep((step) => step + 1);
  };

  const confirmSuggestion = () => {
    if (!selectedSuggestion) return;
    if (onComplete) return onComplete(selectedSuggestion);
    navigate('/app/prompts/new', { state: { suggestion: selectedSuggestion } });
  };

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-8">
        <div className="flex items-center justify-between text-caption text-muted">
          <span>{t('lifecycle.wizard.stepProgress', { current: currentStep + 1, total: totalSteps })}</span>
          <span>{Math.round(((currentStep + 1) / totalSteps) * 100)}%</span>
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-subtle">
          <div className="h-full rounded-full bg-primary transition-all duration-300" style={{ width: `${((currentStep + 1) / totalSteps) * 100}%` }} />
        </div>
      </div>

      <div className="mb-8 min-h-80">
        {isSuggestionStep ? (
          <WizardSuggestions
            suggestions={suggestionMutation.data}
            selectedId={selectedSuggestion?.id}
            pending={suggestionMutation.isPending}
            error={suggestionMutation.isError}
            onRetry={generateSuggestions}
            onSelect={setSelectedSuggestion}
          />
        ) : currentStepData ? (
          <WizardQuestionStep
            step={currentStepData}
            value={currentValue}
            error={typeof fieldError === 'string' ? fieldError : undefined}
            onChange={(value) => form.setValue(currentStepData.id, value as never, { shouldDirty: true, shouldValidate: true })}
          />
        ) : null}
      </div>

      <div className="flex items-center justify-between border-t border-border pt-6">
        <div>{currentStep > 0 ? <Button intent="ghost" leadingIcon={<ArrowLeft aria-hidden className="size-4" />} onClick={() => setCurrentStep((step) => step - 1)}>{t('lifecycle.wizard.back')}</Button> : null}</div>
        <div className="flex gap-3">
          {onCancel ? <Button intent="ghost" onClick={onCancel}>{t('lifecycle.wizard.cancel')}</Button> : null}
          {isSuggestionStep ? (
            <Button disabled={!selectedSuggestion} onClick={confirmSuggestion} leadingIcon={<Check aria-hidden className="size-4" weight="bold" />}>{t('lifecycle.wizard.confirmAndEdit')}</Button>
          ) : (
            <Button disabled={!hasCurrentAnswer} onClick={() => void goNext()} trailingIcon={<ArrowRight aria-hidden className="size-4" />}>
              {currentStep === steps.length - 1 ? t('lifecycle.wizard.generate') : t('lifecycle.wizard.next')}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
