import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';

interface PromptTestInputPanelProps {
  inputPrompt: string;
  variables: string[];
  values: Record<string, string>;
  onInputPromptChange: (value: string) => void;
  onVariableChange: (name: string, value: string) => void;
}

export function PromptTestInputPanel({ inputPrompt, variables, values, onInputPromptChange, onVariableChange }: PromptTestInputPanelProps) {
  const { t } = useTranslation();
  return (
    <Card title={t('lifecycle.promptTest.inputTitle')} className="h-full">
      <Textarea
        label={t('lifecycle.promptTest.inputPrompt')}
        placeholder={t('lifecycle.promptTest.inputPlaceholder')}
        value={inputPrompt}
        onChange={(event) => onInputPromptChange(event.target.value)}
        className="min-h-36"
      />
      {variables.length ? (
        <fieldset className="grid gap-4 border-t border-border pt-4">
          <legend className="sr-only">{t('lifecycle.promptTest.variables')}</legend>
          {variables.map((variable) => (
            <Input
              key={variable}
              label={`{{${variable}}}`}
              placeholder={t('lifecycle.promptTest.variablePlaceholder', { name: variable })}
              value={values[variable] ?? ''}
              onChange={(event) => onVariableChange(variable, event.target.value)}
            />
          ))}
        </fieldset>
      ) : (
        <p className="rounded-xl border border-border bg-subtle p-4 text-caption text-muted">
          {t('lifecycle.promptTest.noVariables')}
        </p>
      )}
    </Card>
  );
}
