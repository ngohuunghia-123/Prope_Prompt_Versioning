import { Sparkle, ArrowRight, ArrowLeft, Check, ChatCircle } from '@phosphor-icons/react';
import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/Card';
import { Select, type SelectOption } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { Radio } from '@/components/ui/Radio';
import type { EditorSuggestion } from '@/features/prompt-lifecycle/types';

export interface PromptEditorQuestionnaireProps {
  onApply: (suggestion: EditorSuggestion) => { ok: true } | { ok: false; reason: 'parse' };
}

interface FormData {
  industry: string;
  primaryGoal: string;
  targetAudience: string;
  tone: string;
  constraints: string;
}

const TOTAL_STEPS = 5;

export function PromptEditorQuestionnaire({ onApply }: PromptEditorQuestionnaireProps) {
  const { t } = useTranslation();
  const [step, setStep] = useState(0);
  const [isGenerating, setIsGenerating] = useState(false);
  const [suggestions, setSuggestions] = useState<EditorSuggestion[]>([]);
  const [formData, setFormData] = useState<FormData>({
    industry: '',
    primaryGoal: '',
    targetAudience: '',
    tone: '',
    constraints: '',
  });

  const updateField = useCallback(<K extends keyof FormData>(key: K, value: FormData[K]) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
  }, []);

  const industryOptions: SelectOption[] = [
    { value: 'customer-support', label: t('lifecycle.questionnaire.industries.customerSupport') },
    { value: 'marketing', label: t('lifecycle.questionnaire.industries.marketing') },
    { value: 'software-engineering', label: t('lifecycle.questionnaire.industries.softwareEngineering') },
    { value: 'sales', label: t('lifecycle.questionnaire.industries.sales') },
    { value: 'education', label: t('lifecycle.questionnaire.industries.education') },
    { value: 'healthcare', label: t('lifecycle.questionnaire.industries.healthcare') },
    { value: 'other', label: t('lifecycle.questionnaire.industries.other') },
  ];

  const targetAudienceOptions: SelectOption[] = [
    { value: 'end-customers', label: t('lifecycle.questionnaire.audiences.endCustomers') },
    { value: 'internal-team', label: t('lifecycle.questionnaire.audiences.internalTeam') },
    { value: 'developers', label: t('lifecycle.questionnaire.audiences.developers') },
    { value: 'mixed', label: t('lifecycle.questionnaire.audiences.mixed') },
  ];

  const primaryGoalOptions = [
    { value: 'reduce-hallucinations', label: t('lifecycle.questionnaire.goals.reduceHallucinations') },
    { value: 'safety-constraints', label: t('lifecycle.questionnaire.goals.safetyConstraints') },
    { value: 'format-output', label: t('lifecycle.questionnaire.goals.formatOutput') },
    { value: 'brand-voice', label: t('lifecycle.questionnaire.goals.brandVoice') },
    { value: 'improve-accuracy', label: t('lifecycle.questionnaire.goals.improveAccuracy') },
  ];

  const toneOptions = [
    { value: 'professional', label: t('lifecycle.questionnaire.tones.professional') },
    { value: 'friendly', label: t('lifecycle.questionnaire.tones.friendly') },
    { value: 'concise', label: t('lifecycle.questionnaire.tones.concise') },
    { value: 'empathetic', label: t('lifecycle.questionnaire.tones.empathetic') },
  ];

  const generateSuggestions = useCallback(async () => {
    setIsGenerating(true);
    await new Promise((resolve) => setTimeout(resolve, 1500));

    const { primaryGoal } = formData;
    let generated: EditorSuggestion[];

    switch (primaryGoal) {
      case 'reduce-hallucinations':
        generated = [{
          id: 'q-grounding',
          kind: 'grounding',
          title: t('lifecycle.questionnaire.suggestions.grounding.title'),
          body: t('lifecycle.questionnaire.suggestions.grounding.body'),
          applyTo: 'append',
        }];
        break;
      case 'safety-constraints':
        generated = [{
          id: 'q-refusal',
          kind: 'refusal',
          title: t('lifecycle.questionnaire.suggestions.refusal.title'),
          body: t('lifecycle.questionnaire.suggestions.refusal.body'),
          applyTo: 'append',
        }];
        break;
      case 'format-output':
        generated = [{
          id: 'q-format',
          kind: 'format',
          title: t('lifecycle.questionnaire.suggestions.format.title'),
          body: t('lifecycle.questionnaire.suggestions.format.body'),
          applyTo: 'append',
        }];
        break;
      default:
        generated = [
          {
            id: 'q-grounding-default',
            kind: 'grounding',
            title: t('lifecycle.questionnaire.suggestions.grounding.title'),
            body: t('lifecycle.questionnaire.suggestions.grounding.body'),
            applyTo: 'append',
          },
          {
            id: 'q-refusal-default',
            kind: 'refusal',
            title: t('lifecycle.questionnaire.suggestions.refusal.title'),
            body: t('lifecycle.questionnaire.suggestions.refusal.body'),
            applyTo: 'append',
          },
          {
            id: 'q-format-default',
            kind: 'format',
            title: t('lifecycle.questionnaire.suggestions.format.title'),
            body: t('lifecycle.questionnaire.suggestions.format.body'),
            applyTo: 'append',
          },
        ];
    }

    setSuggestions(generated);
    setIsGenerating(false);
  }, [formData, t]);

  const canGoNext = () => {
    switch (step) {
      case 0: return Boolean(formData.industry);
      case 1: return Boolean(formData.primaryGoal);
      case 2: return Boolean(formData.targetAudience);
      case 3: return Boolean(formData.tone);
      case 4: return true;
      default: return false;
    }
  };

  const handleNext = async () => {
    if (step < TOTAL_STEPS - 1) {
      setStep((s) => s + 1);
    } else {
      await generateSuggestions();
    }
  };

  const handleBack = () => {
    if (suggestions.length > 0) {
      setSuggestions([]);
    } else {
      setStep((s) => Math.max(0, s - 1));
    }
  };

  const handleReset = () => {
    setStep(0);
    setSuggestions([]);
    setFormData({ industry: '', primaryGoal: '', targetAudience: '', tone: '', constraints: '' });
  };

  return (
    <Card title={t('lifecycle.questionnaire.title')}>
      <div className="flex flex-col gap-5">
        {!isGenerating && suggestions.length === 0 && (
          <p className="text-body text-muted">{t('lifecycle.questionnaire.description')}</p>
        )}

        {isGenerating ? (
          <div className="flex flex-col items-center justify-center gap-4 py-12">
            <div className="relative">
              <div className="size-16 animate-pulse rounded-full bg-secondary/20 motion-reduce:animate-none" />
              <Sparkle className="absolute inset-0 m-auto size-8 animate-pulse text-secondary motion-reduce:animate-none" weight="fill" />
            </div>
            <p className="text-body text-muted">{t('lifecycle.questionnaire.generating')}</p>
          </div>
        ) : suggestions.length > 0 ? (
          <div className="grid gap-4 animate-navigation-panel motion-reduce:animate-none">
            <div className="flex items-center justify-between">
              <p className="text-caption font-semibold text-secondary uppercase flex items-center gap-2">
                <Check weight="bold" className="size-4" />
                {t('lifecycle.questionnaire.suggestionsReady')}
              </p>
              <Button type="button" intent="neutral" onClick={handleReset}>
                {t('lifecycle.questionnaire.startOver')}
              </Button>
            </div>
            <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {suggestions.map((suggestion) => (
                <li key={suggestion.id} className="flex flex-col gap-3 rounded-xl border border-border bg-subtle p-4">
                  <span className="flex items-center gap-2 text-caption font-semibold text-secondary uppercase">
                    <Sparkle aria-hidden className="size-4" weight="fill" />
                    {t(`lifecycle.editor.kinds.${suggestion.kind}`)}
                  </span>
                  <strong className="text-body font-semibold text-ink">{suggestion.title}</strong>
                  <p className="text-body text-muted">{suggestion.body}</p>
                  <Button
                    type="button"
                    intent="neutral"
                    onClick={() => onApply(suggestion)}
                  >
                    {t('lifecycle.editor.applySuggestion')}
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="flex flex-col gap-5">
            <div className="flex items-center gap-2">
              <span className="flex size-6 items-center justify-center rounded-full bg-secondary text-caption font-bold text-surface">
                {step + 1}
              </span>
              <span className="text-caption text-muted">
                {t('lifecycle.questionnaire.stepOf', { current: step + 1, total: TOTAL_STEPS })}
              </span>
            </div>

            <div className="min-h-32 animate-navigation-panel motion-reduce:animate-none">
              {step === 0 && (
                <Select
                  label={t('lifecycle.questionnaire.labels.industry')}
                  options={industryOptions}
                  value={formData.industry}
                  onValueChange={(v) => updateField('industry', v)}
                />
              )}
              {step === 1 && (
                <fieldset className="flex flex-col gap-3">
                  <legend className="text-body font-medium text-ink mb-1">
                    {t('lifecycle.questionnaire.labels.primaryGoal')}
                  </legend>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {primaryGoalOptions.map((option) => (
                      <Radio
                        key={option.value}
                        name="primaryGoal"
                        value={option.value}
                        label={option.label}
                        checked={formData.primaryGoal === option.value}
                        onChange={(e) => updateField('primaryGoal', e.target.value)}
                      />
                    ))}
                  </div>
                </fieldset>
              )}
              {step === 2 && (
                <Select
                  label={t('lifecycle.questionnaire.labels.targetAudience')}
                  options={targetAudienceOptions}
                  value={formData.targetAudience}
                  onValueChange={(v) => updateField('targetAudience', v)}
                />
              )}
              {step === 3 && (
                <fieldset className="flex flex-col gap-3">
                  <legend className="text-body font-medium text-ink mb-1">
                    {t('lifecycle.questionnaire.labels.tone')}
                  </legend>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {toneOptions.map((option) => (
                      <Radio
                        key={option.value}
                        name="tone"
                        value={option.value}
                        label={option.label}
                        checked={formData.tone === option.value}
                        onChange={(e) => updateField('tone', e.target.value)}
                      />
                    ))}
                  </div>
                </fieldset>
              )}
              {step === 4 && (
                <Textarea
                  label={t('lifecycle.questionnaire.labels.constraints')}
                  placeholder={t('lifecycle.questionnaire.constraintsPlaceholder')}
                  value={formData.constraints}
                  onChange={(e) => updateField('constraints', e.target.value)}
                  hint={t('lifecycle.questionnaire.constraintsHint')}
                />
              )}
            </div>

            <div className="flex items-center justify-between gap-3 pt-2">
              <Button
                type="button"
                intent="neutral"
                onClick={handleBack}
                disabled={step === 0 && suggestions.length === 0}
              >
                <ArrowLeft aria-hidden className="size-4" />
                {t('lifecycle.questionnaire.back')}
              </Button>

              <div className="flex items-center gap-2">
                {Array.from({ length: TOTAL_STEPS }).map((_, i) => (
                  <span
                    key={i}
                    className={`size-2 rounded-full transition-colors ${
                      i === step ? 'bg-secondary' : i < step ? 'bg-secondary/40' : 'bg-border'
                    }`}
                  />
                ))}
              </div>

              <Button
                type="button"
                intent="primary"
                onClick={handleNext}
                disabled={!canGoNext()}
              >
                {step < TOTAL_STEPS - 1 ? (
                  <>
                    {t('lifecycle.questionnaire.next')}
                    <ArrowRight aria-hidden className="size-4" />
                  </>
                ) : (
                  <>
                    <Sparkle aria-hidden className="size-4" weight="fill" />
                    {t('lifecycle.questionnaire.generate')}
                  </>
                )}
              </Button>
            </div>
          </div>
        )}

        {step === 0 && !formData.industry && (
          <button
            type="button"
            onClick={() => setSuggestions([{
              id: 'q-default-1',
              kind: 'grounding',
              title: t('lifecycle.questionnaire.suggestions.grounding.title'),
              body: t('lifecycle.questionnaire.suggestions.grounding.body'),
              applyTo: 'append',
            }, {
              id: 'q-default-2',
              kind: 'refusal',
              title: t('lifecycle.questionnaire.suggestions.refusal.title'),
              body: t('lifecycle.questionnaire.suggestions.refusal.body'),
              applyTo: 'append',
            }, {
              id: 'q-default-3',
              kind: 'format',
              title: t('lifecycle.questionnaire.suggestions.format.title'),
              body: t('lifecycle.questionnaire.suggestions.format.body'),
              applyTo: 'append',
            }])}
            className="flex items-center justify-center gap-2 rounded-lg border border-dashed border-border p-3 text-caption text-muted hover:border-secondary hover:text-secondary transition-colors cursor-pointer"
          >
            <ChatCircle aria-hidden className="size-4" />
            {t('lifecycle.questionnaire.skipQuestionnaire')}
          </button>
        )}
      </div>
    </Card>
  );
}
