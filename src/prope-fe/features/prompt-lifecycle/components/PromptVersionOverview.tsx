import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, Copy, GitDiff } from '@phosphor-icons/react';
import { Button } from '@/components/ui/Button';
import { RevisionBindingDisplay } from '@/features/prompt-lifecycle/components/RevisionBindingDisplay';
import type { PromptDetail, Revision } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { PromptBlockAccordion } from '@/features/prompt-lifecycle/components/PromptBlockAccordion';
import { promptBodyForCopy } from '@/features/prompt-lifecycle/xmlBlocks';
import { useWorkspaceDisplayNames } from '@/features/prompt-lifecycle/useWorkspaceDisplayNames';

/** How long the button says it copied before going back to offering to. */
const COPIED_FEEDBACK_MS = 1600;

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
  const [copied, setCopied] = useState(false);
  const format = useLocaleFormatters();
  const { folderName, userName } = useWorkspaceDisplayNames();
  const variables = extractVariables(promptBody);
  const version = revision.number.replace(/^r/, '');
  const folderId = prompt.folderId ?? prompt.modelName.split('/')[0];

  /**
   * The whole body onto the clipboard, blocks collapsed or not.
   *
   * The accordion below shows this prompt one block at a time and a reader who
   * wants to run it elsewhere would otherwise open every block and select
   * across them. `promptBodyForCopy` is what decides how much of the storage
   * shape comes along.
   *
   * A refusal (an insecure origin, a denied permission) leaves the icon alone
   * rather than claiming a copy that did not happen.
   */
  const copyPromptBody = async () => {
    try {
      await navigator.clipboard.writeText(promptBodyForCopy(promptBody));
    } catch {
      return;
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), COPIED_FEEDBACK_MS);
  };

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
          {/* One cell, from the revision on screen. Two cells reading
              `prompt.providerModel` and `prompt.provider` said `noBinding`
              twice about a routed revision — a lie, because it is bound to
              three things — and said the LATEST revision's provider whichever
              revision was being browsed. A route is per-revision by
              construction, so the second half was no longer survivable. */}
          <div className="border-b border-border p-4 sm:col-span-2 xl:border-r xl:border-b-0"><dt className="text-caption text-muted">{t('lifecycle.promptDetail.binding')}</dt><dd className="mt-2"><RevisionBindingDisplay revision={revision} /></dd></div>
          <div className="p-4 sm:border-l">
            <dt className="text-caption text-muted">{t('lifecycle.promptDetail.variables')}</dt>
            <dd className="mt-2 text-body font-semibold text-ink">{t('lifecycle.promptDetail.variableCount', { count: variables.length })}</dd>
            {variables.length > 0 ? <div className="mt-3 flex min-w-0 flex-wrap gap-2">{variables.map((variable) => <code key={variable} className="max-w-full break-all rounded-lg bg-subtle px-2 py-1 text-caption text-link">{`{{${variable}}}`}</code>)}</div> : null}
          </div>
        </dl>
      </section>

      <section aria-labelledby="prompt-content-title">
        <div className="flex flex-wrap items-center justify-between gap-3 p-4 pb-3 sm:px-6">
          <h2 id="prompt-content-title" className="font-display text-heading-3 text-ink">{t('lifecycle.promptDetail.promptContent')}</h2>
          {/* Icon only, and the label lives on `aria-label` rather than beside
              the icon: the heading it sits next to already says what the text
              is, so a word here would only repeat it. */}
          <Button
            type="button"
            intent="neutral"
            size="icon"
            aria-label={t(copied ? 'lifecycle.promptDetail.contentCopied' : 'lifecycle.promptDetail.copyContent')}
            title={t(copied ? 'lifecycle.promptDetail.contentCopied' : 'lifecycle.promptDetail.copyContent')}
            onClick={() => void copyPromptBody()}
          >
            {copied ? <Check aria-hidden className="size-5" /> : <Copy aria-hidden className="size-5" />}
          </Button>
        </div>
        <div className="border-y border-border p-4 sm:p-6"><PromptBlockAccordion beforeBody={previousBody} body={promptBody} /></div>
      </section>
    </div>
  );
}
