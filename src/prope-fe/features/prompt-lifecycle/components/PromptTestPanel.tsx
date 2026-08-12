import { CaretDown, CaretUp, Flask, Play } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

export interface PromptTestPanelProps { variables: string[]; }

export function PromptTestPanel({ variables }: PromptTestPanelProps) {
  const { t } = useTranslation();
  const [values, setValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState('');
  const [open, setOpen] = useState(false);
  const run = () => setResult(JSON.stringify({ status: 'mock_success', variables: Object.fromEntries(variables.map((variable) => [variable, values[variable] ?? ''])) }, null, 2));
  const content = <div className="grid gap-4">{variables.length ? <fieldset className="grid gap-4"><legend className="mb-1 text-body font-semibold text-ink">{t('lifecycle.editor.templateValues')}</legend>{variables.map((variable) => <Input key={variable} label={`{{${variable}}}`} placeholder={t('lifecycle.editor.templateValuePlaceholder')} value={values[variable] ?? ''} onChange={(event) => setValues((current) => ({ ...current, [variable]: event.target.value }))} />)}</fieldset> : <p className="rounded-xl border border-border bg-subtle p-3 text-caption text-muted">{t('lifecycle.editor.noTemplateVariables')}</p>}<Button type="button" intent="secondary" leadingIcon={<Play aria-hidden className="size-4" />} onClick={run}>{t('lifecycle.editor.runTest')}</Button>{result ? <output className="rounded-xl border border-border bg-subtle p-3 text-caption text-ink"><span className="mb-1 block font-semibold">{t('lifecycle.editor.testOutput')}</span><pre className="whitespace-pre-wrap font-mono">{result}</pre></output> : null}</div>;
  return <>
    <section className="hidden self-start rounded-modal border border-border bg-surface p-5 shadow-panel xl:sticky xl:top-24 xl:block"><div className="mb-4"><h2 className="font-display text-heading-3 text-ink">{t('lifecycle.editor.testPrompt')}</h2><p className="mt-1 text-caption text-muted">{t('lifecycle.editor.testDescription')}</p></div>{content}</section>
    {open ? <button type="button" aria-label={t('common.close')} className="fixed inset-0 z-40 cursor-default bg-ink/45 navigation:left-(--workspace-navigation-width) xl:hidden" onClick={() => setOpen(false)} /> : null}
    <section role={open ? 'dialog' : undefined} aria-modal={open || undefined} aria-label={t('lifecycle.editor.testPrompt')} className="fixed inset-x-0 bottom-0 z-50 max-h-dvh overflow-y-auto rounded-t-modal border border-border bg-surface shadow-floating navigation:left-(--workspace-navigation-width) xl:hidden">
      <button type="button" aria-expanded={open} onClick={() => setOpen((current) => !current)} className="flex min-h-14 w-full cursor-pointer items-center justify-between gap-3 px-5 text-left text-ink focus-visible:outline-2 focus-visible:outline-focus"><span className="flex items-center gap-2 font-display text-heading-3"><Flask aria-hidden className="size-5 text-secondary" />{t('lifecycle.editor.testSheet')}</span>{open ? <CaretDown aria-hidden className="size-5 text-muted" /> : <CaretUp aria-hidden className="size-5 text-muted" />}</button>
      {open ? <div className="border-t border-border p-5"><p className="mb-4 text-caption text-muted">{t('lifecycle.editor.testDescription')}</p>{content}</div> : null}
    </section>
  </>;
}
