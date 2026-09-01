import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, Copy, GitDiff } from '@phosphor-icons/react';
import { SegmentedControl } from '@/components/SegmentedControl';
import { Button } from '@/components/ui/Button';
import { Tag } from '@/components/Tag';
import { RevisionBindingDisplay } from '@/features/prompt-lifecycle/components/RevisionBindingDisplay';
import type { PromptDetail, Revision } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { PromptBlockAccordion } from '@/features/prompt-lifecycle/components/PromptBlockAccordion';
import { promptBodyForCopy } from '@/features/prompt-lifecycle/xmlBlocks';
import type { XmlEditorMode } from '@/features/prompt-lifecycle/useXmlBlockEditor';
import { useWorkspaceDisplayNames } from '@/features/prompt-lifecycle/useWorkspaceDisplayNames';

/** How long the button says it copied before going back to offering to. */
const COPIED_FEEDBACK_MS = 1600;

interface PromptVersionOverviewProps {
  prompt: PromptDetail;
  revision: Revision;
  promptBody: string;
  previousBody?: string;
  /** Absent when the panel is showing a draft: comparison pairs saved
   * versions, and a draft is not one yet. */
  onCompare?: () => void;
  /** Set when `revision` is a draft display-shape — badges the metadata so the
   * panel never reads as a published version. */
  draftName?: string;
}

function extractVariables(promptBody: string) {
  return [...new Set([...promptBody.matchAll(/{{\s*([^{}]+?)\s*}}/g)].map((match) => match[1]?.trim()).filter((value): value is string => Boolean(value)))];
}

export function PromptVersionOverview({ prompt, revision, promptBody, previousBody, onCompare, draftName }: PromptVersionOverviewProps) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  const [contentView, setContentView] = useState<XmlEditorMode>('blocks');
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
      {/* Content first: a reader who opened this screen came for the prompt
          text itself — metadata and parameters describe it, they are not it. */}
      {/* No heading of its own: the page header already names this panel —
          a second "Prompt content" heading above it was dead weight. */}
      <section aria-label={t('lifecycle.promptDetail.promptContent')}>
        <div className="p-4 pb-3 sm:px-6">
          {/* A named row, not a bare control strip: the page header names the
              prompt, but this panel scrolls far enough that a reader landing
              mid-page needs the subject restated right above the body. One
              style for the whole phrase — splitting the label from the title
              read as two unrelated strings rather than one sentence. */}
          <div className="flex min-w-0 items-center gap-2">
            <span className="min-w-0 truncate font-display text-heading-3 text-ink">{t('lifecycle.promptDetail.promptContentOf', { title: prompt.title })}</span>
          </div>
          {/* Compare and the in-place controls split one row: compare
              navigates away to the comparison workspace (reads as a row-level
              action, so it leads), while the toggle and copy act on the text
              in place — space-between keeps the two purposes apart instead of
              wrapping messily at this column width. */}
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            {onCompare ? <Button intent="neutral" size="small" leadingIcon={<GitDiff aria-hidden className="size-4" />} onClick={onCompare}>{t('lifecycle.promptCompare.action')}</Button> : null}
            <div className="flex items-center gap-2">
            {/* w-auto overrides the primitive's `w-full`: the cap below
                (`max-w-44`) was squeezing "Block" into a truncate, so the
                control now sizes to its labels and keeps them whole. Labels
                are styled via `[&_label]` because the padding is on the label
                element itself — scoped here rather than retuned for the
                primitive's seven other call sites. The shared `min-w` makes
                both labels the same width: the primitive paints its active
                pill at exactly half the control, so unequal labels ("Blocks"
                is 17px wider than "XML") left the active label's text
                spilling past the pill edge on one side. `gap-0` closes the
                primitive's 4px inter-label gap, which its pill math ignores —
                the pill sizes to (100% - 8px) / 2 = 86px while a gap split
                the labels at 84px, leaving the pill 2px wider than its label
                and the active text visibly off-center inside it. */}
            <SegmentedControl
              className="w-auto gap-0 [&_label]:min-w-21 [&_label]:px-3"
              label={t('lifecycle.promptDetail.viewMode')}
              name="prompt-content-view"
              options={[
                { value: 'blocks', label: t('lifecycle.xml.blocks') },
                { value: 'xml', label: t('lifecycle.xml.xml') },
              ]}
              value={contentView}
              onValueChange={(next) => setContentView(next as XmlEditorMode)}
            />
            {/* Icon only, and the label lives on `aria-label` rather than beside
                the icon: the heading it sits next to already says what the text
                is, so a word here would only repeat it. */}
            {/* The icon button matches the segmented control's 42px footprint
                (its 34px pill + 4px padding ring) instead of the `size="icon"`
                40px square, so the pair reads as one control row. `!p-0` wins
                over the `button-content` padding (8px 14px) that would leave a
                14px content box and crop the 18px glyph; the glyph scales up
                via `[&_svg]` because Button wraps icon-only children in a
                span, hiding `>svg` selectors. */}
            <Button
              type="button"
              intent="neutral"
              aria-label={t(copied ? 'lifecycle.promptDetail.contentCopied' : 'lifecycle.promptDetail.copyContent')}
              title={t(copied ? 'lifecycle.promptDetail.contentCopied' : 'lifecycle.promptDetail.copyContent')}
              onClick={() => void copyPromptBody()}
              className="size-10.5 rounded-full !p-0 [&_svg]:size-4.5"
            >
              {copied ? <Check aria-hidden /> : <Copy aria-hidden />}
            </Button>
            </div>
          </div>
        </div>
        {contentView === 'blocks' ? (
          <div className="border-y border-border p-4 sm:p-6"><PromptBlockAccordion beforeBody={previousBody} body={promptBody} defaultExpanded /></div>
        ) : (
          <div className="border-y border-border p-4 sm:p-6">
            <div className="max-h-96 overflow-auto rounded-xl border border-border bg-canvas p-4">
              <pre className="whitespace-pre-wrap font-mono text-caption text-ink">{promptBody}</pre>
            </div>
          </div>
        )}
      </section>

      <section aria-labelledby="prompt-parameters-title">
        <h2 id="prompt-parameters-title" className="p-4 pb-3 font-display text-heading-3 text-ink sm:px-6">{t('lifecycle.promptDetail.parameters')}</h2>
        {/* Even halves, not a 2:1 span: `sm:grid-cols-3` + `col-span-2` gave
            the binding cell 443px against the variables cell's 221px at this
            column width — a lopsided split that read as clutter, and its
            border choreography (`xl:border-r` / `xl:border-b-0` vs
            `sm:border-l`) only held together above 1280px. Two equal columns
            with one shared divider hold at every width and collapse to full-
            width rows below `sm`. */}
        <dl className="grid border-y border-border sm:grid-cols-2">
          {/* One cell, from the revision on screen. Two cells reading
              `prompt.providerModel` and `prompt.provider` said `noBinding`
              twice about a routed revision — a lie, because it is bound to
              three things — and said the LATEST revision's provider whichever
              revision was being browsed. A route is per-revision by
              construction, so the second half was no longer survivable. */}
          <div className="border-b border-border p-4 sm:border-b-0 sm:border-r sm:px-6"><dt className="text-caption text-muted">{t('lifecycle.promptDetail.binding')}</dt><dd className="mt-2"><RevisionBindingDisplay revision={revision} /></dd></div>
          <div className="p-4 sm:px-6">
            <dt className="text-caption text-muted">{t('lifecycle.promptDetail.variables')}</dt>
            <dd className="mt-2 text-body font-semibold text-ink">{t('lifecycle.promptDetail.variableCount', { count: variables.length })}</dd>
            {variables.length > 0 ? <div className="mt-3 flex min-w-0 flex-wrap gap-2">{variables.map((variable) => <code key={variable} className="max-w-full break-all rounded-lg bg-subtle px-2 py-1 text-caption text-link">{`{{${variable}}}`}</code>)}</div> : null}
          </div>
        </dl>
      </section>

      <section aria-labelledby="prompt-metadata-title">
        <div className="p-4 pb-3 sm:px-6"><h2 id="prompt-metadata-title" className="font-display text-heading-3 text-ink">{t('lifecycle.promptDetail.metadata')}</h2></div>
        {/* Cell borders, not bare two-column rows: `gap-x-8 gap-y-3` left the
            pairs floating with no shared rhythm — label/value baselines
            misaligned between columns whenever one wrapped, and on mobile the
            loose stack read as one undifferentiated list. Bordered cells with
            the same padding as the parameters section tie the two blocks into
            one visual system, and each cell stacks full-width below `sm`. */}
        <dl className="grid border-t border-border sm:grid-cols-2">
          <div className="border-b border-border p-4 sm:px-6"><dt className="text-caption text-muted">{t('lifecycle.promptDetail.name')}</dt><dd className="mt-1 text-body font-semibold text-ink">{prompt.title}</dd></div>
          <div className="border-b border-border p-4 sm:border-l sm:px-6"><dt className="text-caption text-muted">{t('lifecycle.promptDetail.version')}</dt><dd className="mt-1 flex items-center gap-2 text-body font-semibold text-ink">{version}{draftName ? <Tag state="neutral" className="px-2 py-1">{t('lifecycle.promptDetail.draftBadge')}</Tag> : null}</dd></div>
          <div className="border-b border-border p-4 sm:px-6"><dt className="text-caption text-muted">{t('lifecycle.promptDetail.folder')}</dt><dd className="mt-1 text-body text-ink">{folderName(folderId)}</dd></div>
          <div className="border-b border-border p-4 sm:border-l sm:px-6"><dt className="text-caption text-muted">{t('lifecycle.promptDetail.createdAt')}</dt><dd className="mt-1 text-body text-ink">{format.date(revision.createdAt)}</dd></div>
          <div className="border-b border-border p-4 sm:px-6"><dt className="text-caption text-muted">{t('lifecycle.promptDetail.author')}</dt><dd className="mt-1 text-body text-ink">{userName(revision.author)}</dd></div>
          <div className="border-b border-border p-4 sm:border-l sm:px-6"><dt className="text-caption text-muted">{t('lifecycle.overview.versioning.changeSummary')}</dt><dd className="mt-1 text-body text-ink">{revision.summary}</dd></div>
          <div className="border-b border-border p-4 sm:col-span-2 sm:border-l-0 sm:px-6"><dt className="text-caption text-muted">{t('lifecycle.promptDetail.fallback')}</dt><dd className="mt-1 whitespace-pre-wrap text-body text-ink">{prompt.fallbackAnswer}</dd></div>
        </dl>
      </section>
    </div>
  );
}
