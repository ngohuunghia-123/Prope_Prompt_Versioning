import { useTranslation } from 'react-i18next';
import type { PromptDetail, Revision } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';

interface PromptVersionOverviewProps {
  prompt: PromptDetail;
  revision: Revision;
  promptBody: string;
}

function extractVariables(promptBody: string) {
  return [...new Set([...promptBody.matchAll(/{{\s*([^{}]+?)\s*}}/g)].map((match) => match[1]?.trim()).filter((value): value is string => Boolean(value)))];
}

export function PromptVersionOverview({ prompt, revision, promptBody }: PromptVersionOverviewProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const variables = extractVariables(promptBody);
  const version = revision.number.replace(/^r/, '');

  return (
    <div className="grid gap-7 p-4 sm:p-6 lg:p-8">
      <section aria-labelledby="prompt-metadata-title">
        <h2 id="prompt-metadata-title" className="mb-3 font-display text-heading-3 text-ink">{t('lifecycle.promptDetail.metadata')}</h2>
        <dl className="grid gap-x-8 gap-y-3 rounded-modal border border-border bg-surface p-5 shadow-panel sm:grid-cols-2">
          <div><dt className="text-caption text-muted">{t('lifecycle.promptDetail.name')}</dt><dd className="mt-1 text-body font-semibold text-ink">{prompt.title}</dd></div>
          <div><dt className="text-caption text-muted">{t('lifecycle.promptDetail.version')}</dt><dd className="mt-1 text-body font-semibold text-ink">{version}</dd></div>
          <div><dt className="text-caption text-muted">{t('lifecycle.promptDetail.createdAt')}</dt><dd className="mt-1 text-body text-ink">{format.date(revision.createdAt)}</dd></div>
          <div><dt className="text-caption text-muted">{t('lifecycle.promptDetail.author')}</dt><dd className="mt-1 text-body text-ink">{revision.author}</dd></div>
        </dl>
      </section>

      <section aria-labelledby="prompt-parameters-title">
        <h2 id="prompt-parameters-title" className="mb-3 font-display text-heading-3 text-ink">{t('lifecycle.promptDetail.parameters')}</h2>
        <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-xl border border-border bg-surface p-4"><dt className="text-caption text-muted">{t('lifecycle.promptDetail.model')}</dt><dd className="mt-2 text-body font-semibold text-ink">{prompt.providerModel}</dd></div>
          <div className="rounded-xl border border-border bg-surface p-4"><dt className="text-caption text-muted">{t('lifecycle.promptDetail.provider')}</dt><dd className="mt-2 text-body font-semibold text-ink">{prompt.provider}</dd></div>
          <div className="rounded-xl border border-border bg-surface p-4"><dt className="text-caption text-muted">{t('lifecycle.promptDetail.variables')}</dt><dd className="mt-2 text-body font-semibold text-ink">{t('lifecycle.promptDetail.variableCount', { count: variables.length })}</dd></div>
          <div className="rounded-xl border border-border bg-surface p-4"><dt className="text-caption text-muted">{t('lifecycle.promptDetail.evalResult')}</dt><dd className="mt-2 text-body font-semibold text-ink">{revision.evalPassed}/{revision.evalTotal}</dd></div>
        </dl>
        {variables.length > 0 ? <div className="mt-3 flex flex-wrap gap-2">{variables.map((variable) => <code key={variable} className="rounded-lg bg-subtle px-2 py-1 text-caption text-link">{`{{${variable}}}`}</code>)}</div> : null}
      </section>

      <section aria-labelledby="prompt-content-title">
        <h2 id="prompt-content-title" className="mb-3 font-display text-heading-3 text-ink">{t('lifecycle.promptDetail.promptContent')}</h2>
        <pre className="min-h-64 overflow-x-auto whitespace-pre-wrap rounded-modal border border-border bg-surface p-5 font-sans text-body leading-relaxed text-ink shadow-inset">{promptBody}</pre>
      </section>
    </div>
  );
}
