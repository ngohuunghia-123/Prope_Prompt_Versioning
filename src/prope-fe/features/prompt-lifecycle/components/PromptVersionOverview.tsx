import { useTranslation } from 'react-i18next';
import { GitDiff } from '@phosphor-icons/react';
import { Button } from '@/components/ui/Button';
import { useProviderName } from '@/features/prompt-lifecycle/useProviderName';
import type { PromptDetail, Revision } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { PromptBlockAccordion } from '@/features/prompt-lifecycle/components/PromptBlockAccordion';
import { useWorkspaceDisplayNames } from '@/features/prompt-lifecycle/useWorkspaceDisplayNames';

interface PromptVersionOverviewProps {
  prompt: PromptDetail;
  revision: Revision;
  promptBody: string;
  previousBody?: string;
  onCompare: () => void;
}

function extractVariables(promptBody: string) {
  return [...new Set([...promptBody.matchAll(/{{\s*([^{}]+?)\s*}}/g)].map((match) => match[1]?.trim()).filter((value): value is string => Boolean(value)))];
}

export function PromptVersionOverview({ prompt, revision, promptBody, previousBody, onCompare }: PromptVersionOverviewProps) {
  const { t } = useTranslation();
  // `prompt.provider` is the bound configuration's id, not its name.
  const providerName = useProviderName(prompt.provider);
  const format = useLocaleFormatters();
  const { folderName, userName } = useWorkspaceDisplayNames();
  const variables = extractVariables(promptBody);
  const version = revision.number.replace(/^r/, '');
  const folderId = prompt.folderId ?? prompt.modelName.split('/')[0];

  return (
    <div className="divide-y divide-border">
      <section aria-labelledby="prompt-metadata-title" className="p-4 sm:p-6">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3"><h2 id="prompt-metadata-title" className="font-display text-heading-3 text-ink">{t('lifecycle.promptDetail.metadata')}</h2><Button intent="neutral" size="small" leadingIcon={<GitDiff aria-hidden className="size-4" />} onClick={onCompare}>{t('lifecycle.promptCompare.action')}</Button></div>
        <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
          <div><dt className="text-caption text-muted">{t('lifecycle.promptDetail.name')}</dt><dd className="mt-1 text-body font-semibold text-ink">{prompt.title}</dd></div>
          <div><dt className="text-caption text-muted">{t('lifecycle.promptDetail.version')}</dt><dd className="mt-1 text-body font-semibold text-ink">{version}</dd></div>
          <div><dt className="text-caption text-muted">{t('lifecycle.promptDetail.folder')}</dt><dd className="mt-1 text-body text-ink">{folderName(folderId)}</dd></div>
          <div><dt className="text-caption text-muted">{t('lifecycle.promptDetail.createdAt')}</dt><dd className="mt-1 text-body text-ink">{format.date(revision.createdAt)}</dd></div>
          <div><dt className="text-caption text-muted">{t('lifecycle.promptDetail.author')}</dt><dd className="mt-1 text-body text-ink">{userName(revision.author)}</dd></div>
          <div><dt className="text-caption text-muted">{t('lifecycle.overview.versioning.changeSummary')}</dt><dd className="mt-1 text-body text-ink">{revision.summary}</dd></div>
          <div className="sm:col-span-2"><dt className="text-caption text-muted">{t('lifecycle.promptDetail.fallback')}</dt><dd className="mt-1 whitespace-pre-wrap text-body text-ink">{prompt.fallbackAnswer}</dd></div>
        </dl>
      </section>

      <section aria-labelledby="prompt-parameters-title">
        <h2 id="prompt-parameters-title" className="p-4 pb-3 font-display text-heading-3 text-ink sm:px-6">{t('lifecycle.promptDetail.parameters')}</h2>
        <dl className="grid border-y border-border sm:grid-cols-3">
          <div className="border-b border-border p-4 xl:border-r xl:border-b-0"><dt className="text-caption text-muted">{t('lifecycle.promptDetail.model')}</dt><dd className="mt-2 text-body font-semibold text-ink">{prompt.providerModel || t('lifecycle.promptDetail.noBinding')}</dd></div>
          <div className="border-b border-border p-4 sm:border-l"><dt className="text-caption text-muted">{t('lifecycle.promptDetail.provider')}</dt><dd className="mt-2 text-body font-semibold text-ink">{providerName ?? t('lifecycle.promptDetail.noBinding')}</dd></div>
          <div className="p-4 sm:border-l">
            <dt className="text-caption text-muted">{t('lifecycle.promptDetail.variables')}</dt>
            <dd className="mt-2 text-body font-semibold text-ink">{t('lifecycle.promptDetail.variableCount', { count: variables.length })}</dd>
            {variables.length > 0 ? <div className="mt-3 flex min-w-0 flex-wrap gap-2">{variables.map((variable) => <code key={variable} className="max-w-full break-all rounded-lg bg-subtle px-2 py-1 text-caption text-link">{`{{${variable}}}`}</code>)}</div> : null}
          </div>
        </dl>
      </section>

      <section aria-labelledby="prompt-content-title">
        <h2 id="prompt-content-title" className="p-4 pb-3 font-display text-heading-3 text-ink sm:px-6">{t('lifecycle.promptDetail.promptContent')}</h2>
        <div className="border-y border-border p-4 sm:p-6"><PromptBlockAccordion beforeBody={previousBody} body={promptBody} /></div>
      </section>
    </div>
  );
}
