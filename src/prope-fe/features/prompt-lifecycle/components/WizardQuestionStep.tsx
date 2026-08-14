import { Check } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Textarea } from '@/components/ui/Textarea';
import type { WizardAnswers, WizardStep } from '@/features/prompt-lifecycle/types';
import { cn } from '@/lib/cn';

interface WizardQuestionStepProps {
  step: WizardStep;
  value: WizardAnswers[keyof WizardAnswers] | undefined;
  error?: string;
  onChange: (value: string | string[]) => void;
}

export function WizardQuestionStep({ step, value, error, onChange }: WizardQuestionStepProps) {
  const { t } = useTranslation();
  const question = t(`lifecycle.wizard.${step.questionKey}`);

  if (!step.options) {
    return (
      <Textarea
        label={question}
        placeholder={step.placeholderKey ? t(`lifecycle.wizard.${step.placeholderKey}`) : undefined}
        value={typeof value === 'string' ? value : ''}
        error={error}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-32"
      />
    );
  }

  return (
    <fieldset className="space-y-4">
      <legend className="font-display text-heading-2 text-ink">{question}</legend>
      <div className="grid gap-3">
        {step.options.map((option) => {
          const isSelected = Array.isArray(value) ? value.includes(option.value) : value === option.value;
          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={isSelected}
              onClick={() => {
                if (!step.multiSelect) return onChange(option.value);
                const current = Array.isArray(value) ? value : [];
                onChange(isSelected ? current.filter((item) => item !== option.value) : [...current, option.value]);
              }}
              className={cn(
                'flex items-center gap-3 rounded-modal border bg-surface p-4 text-left transition-colors focus-visible:outline-2 focus-visible:outline-focus',
                isSelected ? 'border-primary bg-primary/5 ring-2 ring-primary/20' : 'border-border hover:border-primary/50',
              )}
            >
              <span className={cn('flex size-5 shrink-0 items-center justify-center rounded-sm border-2', isSelected ? 'border-primary bg-primary' : 'border-muted')}>
                {isSelected ? <Check aria-hidden className="size-3 text-ink" weight="bold" /> : null}
              </span>
              <span className="text-body text-ink">{t(`lifecycle.wizard.${option.labelKey}`)}</span>
            </button>
          );
        })}
      </div>
      {error ? <p className="text-caption text-danger-text">{error}</p> : null}
    </fieldset>
  );
}
