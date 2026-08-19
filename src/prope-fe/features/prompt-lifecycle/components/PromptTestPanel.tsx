import { Play } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

export interface PromptTestPanelProps { variables: string[]; }

export function PromptTestPanel({ variables }: PromptTestPanelProps) {
  const { t } = useTranslation();
  const [values, setValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState('');
  const run = () => setResult(JSON.stringify({ status: 'mock_success', variables: Object.fromEntries(variables.map((variable) => [variable, values[variable] ?? ''])) }, null, 2));
  const content = <div className="grid gap-4">{variables.length ? <fieldset className="grid gap-4"><legend className="mb-1 text-body font-semibold text-ink">{t('lifecycle.editor.templateValues')}</legend>{variables.map((variable) => <Input key={variable} label={`{{${variable}}}`} placeholder={t('lifecycle.editor.templateValuePlaceholder')} value={values[variable] ?? ''} onChange={(event) => setValues((current) => ({ ...current, [variable]: event.target.value }))} />)}</fieldset> : <p className="rounded-xl border border-border bg-subtle p-3 text-caption text-muted">{t('lifecycle.editor.noTemplateVariables')}</p>}<Button type="button" intent="secondary" leadingIcon={<Play aria-hidden className="size-4" />} onClick={run}>{t('lifecycle.editor.runTest')}</Button>{result ? <output className="rounded-xl border border-border bg-subtle p-3 text-caption text-ink"><span className="mb-1 block font-semibold">{t('lifecycle.editor.testOutput')}</span><pre className="whitespace-pre-wrap font-mono">{result}</pre></output> : null}</div>;
  return <section className="hidden self-start rounded-modal border border-border bg-surface p-5 shadow-panel xl:sticky xl:top-24 xl:block"><div className="mb-4"><h2 className="font-display text-heading-3 text-ink">{t('lifecycle.editor.testPrompt')}</h2><p className="mt-1 text-caption text-muted">{t('lifecycle.editor.testDescription')}</p></div>{content}</section>;
}
