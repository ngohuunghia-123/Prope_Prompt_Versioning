import { Sparkle } from '@phosphor-icons/react';
import { useEffect, useMemo, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { Tag } from '@/components/Tag';
import { Modal } from '@/components/ui/Modal';
import { Radio } from '@/components/ui/Radio';
import { cn } from '@/lib/cn';
import { WordHeatmap } from '@/features/prompt-lifecycle/components/WordHeatmap';
import { sharedWordsOf } from '@/features/prompt-lifecycle/wordOverlap';
import { parseXmlBlocks } from '@/features/prompt-lifecycle/xmlBlocks';
import type {
  ComparisonCandidate,
  ComparisonFinding,
  ComparisonOverlap,
  PromptSearchResult,
} from '@/features/prompt-lifecycle/types';

const NEW_PROMPT = '__new__';

export interface SimilarPromptsDialogProps {
  open: boolean;
  reviewOnly?: boolean;
  matches: PromptSearchResult[];
  /** One classification per row of `matches`, joined by `prompt_id`. */
  candidates?: ComparisonCandidate[];
  /** Findings about the answer itself rather than about a candidate. */
  coverage?: ComparisonFinding[];
  /** What to pre-select. `undefined` means "create a new prompt". */
  recommendedTarget?: string;
  /** How wide each rung of the funnel was. Shown as *what was checked*, which is
   * a different number from what is listed. */
  retrieved?: number;
  adjudicated?: number;
  /** The floor every listed row cleared, and how many were held back by it. */
  matchFloor?: number;
  belowFloor?: number;
  sourceText: string;
  onContinue: (target: string | undefined) => void;
  onStop: () => void;
}

/** A finding's params, with arrays flattened so `{{added}}` reads as a list.
 *
 * The wire carries machine values — variable names, output keys, counts — and
 * never a sentence (ADR-0053). The sentence is in the catalogue; this is only
 * the join, and it is here rather than on the server because a comma is a
 * language's punctuation and not a fact about the finding. */
function interpolation(finding: ComparisonFinding): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(finding.params ?? {}).map(([key, value]) => [
      key,
      Array.isArray(value) ? value.join(', ') : value,
    ]),
  );
}

const SEVERITY_STATE = { hard: 'danger', soft: 'warning', info: 'neutral' } as const;

const percent = (value: number) => Math.round(value * 100);

function FindingRow({ finding }: { finding: ComparisonFinding }) {
  const { t } = useTranslation();
  const key = `lifecycle.similarity.findings.${finding.code.replace(/^similar\./, '')}`;
  return (
    <li className="flex items-start gap-2">
      <Tag state={SEVERITY_STATE[finding.severity]}>{t(`lifecycle.similarity.severity.${finding.severity}`)}</Tag>
      <span className="pt-1.5 text-caption leading-relaxed text-muted">{t(key, interpolation(finding))}</span>
    </li>
  );
}

/** One measurement, with its own name, its own scale, and its own "not measured".
 *
 * `value === null` renders as *not measured* and never as `0%`. The two are
 * different claims and only one of them is evidence: a candidate that shares
 * none of the incoming prompt's output contract is a strong signal, and a
 * candidate whose prompt declares no output contract at all is silence. This is
 * `output_contract.not_established` applied one layer up — *not established*
 * has never meant *compatible* in this package and must not start meaning
 * *incompatible* here either. */
function Metric({
  label,
  value,
  detail,
  emphasis = false,
}: {
  label: string;
  value: number | null;
  detail?: string;
  emphasis?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <div className="grid content-start gap-1">
      <span className="text-caption leading-tight text-muted">{label}</span>
      <span className={cn('text-caption font-semibold tabular-nums', emphasis ? 'text-ink' : 'text-muted')}>
        {value === null ? t('lifecycle.similarity.metrics.unmeasured') : `${percent(value)}%`}
      </span>
      <div className="h-1 w-full overflow-hidden rounded-full bg-subtle" aria-hidden>
        {value === null ? null : (
          <div
            className={cn('h-full rounded-full', emphasis ? 'bg-primary' : 'bg-secondary')}
            style={{ width: `${percent(value)}%` }}
          />
        )}
      </div>
      {detail ? <span className="text-caption leading-tight text-muted">{detail}</span> : null}
    </div>
  );
}

/** The five measurements behind a row, instead of the one number that hid them.
 *
 * **A single "98%" is the whole-document embedding's mistake in miniature.** It
 * is a weighted average over heterogeneous evidence — what the job says, what
 * the output contract says, which inputs are read, where the vectors sit — and
 * averaging is exactly how the one axis that mattered gets washed out by four
 * that agreed. Two prompts can cover 98% of each other's wording and still take
 * different variables, which breaks every caller; that fact is a hard finding
 * below and it was invisible in the number above.
 *
 * So the five travel separately and none of them is combined with another here.
 * The roll-up stays as the first tile because the 90% floor is applied to it and
 * a threshold whose number is off the screen cannot be argued with — it is
 * labelled as what it is rather than as "how similar".
 *
 * `vector` is the one that may legitimately be absent: a lexically-matched
 * candidate has no cosine, and inventing one is how a prompt nobody had indexed
 * came to look like a certain duplicate. */
function MetricGrid({
  candidate,
  match,
}: {
  candidate: ComparisonCandidate;
  match: PromptSearchResult | undefined;
}) {
  const { t } = useTranslation();
  const overlap = candidate.overlap;
  const blocks = new Map((overlap?.blocks ?? []).map((block) => [block.block, block.score]));
  const compared = new Set(overlap?.compared_blocks ?? []);

  /** A block's containment: its score, `0` if it was compared and shared
   * nothing, `null` if it was never compared at all. */
  const block = (tag: string): number | null =>
    blocks.get(tag) ?? (compared.has(tag) ? 0 : null);

  // The job, from the `instructions` block — or from whole text when the
  // incoming prompt has not been converted yet, which is the import screen's
  // normal case and is labelled differently rather than passed off as the job.
  const wholeText = block('whole_text');
  const job = block('instructions') ?? wholeText;
  const variables = overlap && overlap.variables_required > 0 ? overlap.variable_overlap : null;

  return (
    <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3 lg:grid-cols-5">
      <Metric
        label={t('lifecycle.similarity.metrics.overall')}
        value={candidate.match_score}
        detail={t('lifecycle.similarity.metrics.overallHint')}
        emphasis
      />
      <Metric
        label={t(
          wholeText !== null && block('instructions') === null
            ? 'lifecycle.similarity.metrics.wholeText'
            : 'lifecycle.similarity.metrics.job',
        )}
        value={job}
      />
      <Metric label={t('lifecycle.similarity.metrics.output')} value={block('output_format')} />
      <Metric
        label={t('lifecycle.similarity.metrics.variables')}
        value={variables}
        detail={
          overlap && overlap.variables_required > 0
            ? t('lifecycle.similarity.metrics.variablesDetail', {
                shared: overlap.shared_variables.length,
                required: overlap.variables_required,
              })
            : t('lifecycle.similarity.metrics.noVariables')
        }
      />
      <Metric
        label={t('lifecycle.similarity.metrics.vector')}
        value={typeof match?.similarity === 'number' ? match.similarity : null}
        detail={typeof match?.similarity === 'number' ? undefined : t('lifecycle.similarity.metrics.lexicalOnly')}
      />
    </div>
  );
}

/** One block's overlap: how much, and — the part worth reading — which words.
 *
 * The bar is deliberately not labelled "similarity". It is containment over
 * IDF-weighted terms: the share of the incoming block's *distinctive* vocabulary
 * this candidate also uses. Two prompts written in one house style share their
 * `system` block almost entirely and that number means nothing, which is exactly
 * why the words are shown beside it. */
function BlockOverlapRow({ block, score, terms }: { block: string; score: number; terms: string[] }) {
  const { t } = useTranslation();
  const label = block === 'whole_text' ? t('lifecycle.similarity.wholeText') : block;
  return (
    <li className="grid gap-1.5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <code className="text-caption font-semibold text-ink">{label}</code>
        <span className="text-caption text-muted">
          {t('lifecycle.similarity.blockShare', { percent: percent(score) })}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-subtle" aria-hidden>
        <div className="h-full rounded-full bg-secondary" style={{ width: `${percent(score)}%` }} />
      </div>
      {terms.length > 0 ? (
        <div className="flex flex-wrap gap-1">
          {terms.map((term) => (
            <span key={term} className="rounded-control bg-secondary/20 px-1.5 py-0.5 text-caption text-ink">
              {term}
            </span>
          ))}
        </div>
      ) : null}
    </li>
  );
}

/** The specifics: what the two prompts share, and what the verdict rests on. */
function HowSimilar({
  candidate,
  match,
  overlap,
}: {
  candidate: ComparisonCandidate;
  match: PromptSearchResult | undefined;
  overlap: ComparisonOverlap | null | undefined;
}) {
  const { t } = useTranslation();
  const blocks = overlap?.blocks ?? [];

  return (
    <div className="grid gap-4">
      {candidate.reasons.length > 0 ? (
        <section className="grid gap-2">
          <h4 className="text-caption font-semibold uppercase tracking-wide text-muted">
            {t('lifecycle.similarity.whyTitle')}
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {candidate.reasons.map((reason) => (
              <Tag key={reason} state="default">
                {t(`lifecycle.similarity.reason.${reason}`, { defaultValue: reason })}
              </Tag>
            ))}
          </div>
        </section>
      ) : null}

      {blocks.length > 0 ? (
        <section className="grid gap-2">
          <h4 className="text-caption font-semibold uppercase tracking-wide text-muted">
            {t('lifecycle.similarity.blockOverlap')}
          </h4>
          <ul className="grid gap-3">
            {blocks.map((block) => (
              <BlockOverlapRow
                key={block.block}
                block={block.block}
                score={block.score}
                terms={block.shared_terms}
              />
            ))}
          </ul>
          <p className="text-caption leading-relaxed text-muted">{t('lifecycle.similarity.blockNote')}</p>
        </section>
      ) : (
        <p className="text-caption text-muted">{t('lifecycle.similarity.howEmpty')}</p>
      )}

      <section className="grid gap-1.5">
        <h4 className="text-caption font-semibold uppercase tracking-wide text-muted">
          {t('lifecycle.similarity.sharedVariables')}
        </h4>
        {overlap && overlap.shared_variables.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {overlap.shared_variables.map((name) => (
              <code key={name} className="rounded-control border border-border px-1.5 py-0.5 text-caption text-ink">
                {`{{${name}}}`}
              </code>
            ))}
          </div>
        ) : (
          <p className="text-caption text-muted">{t('lifecycle.similarity.noSharedVariables')}</p>
        )}
      </section>

      <section className="flex flex-wrap items-center gap-x-4 gap-y-1 text-caption text-muted">
        {match && match.matched_fields.length > 0 ? (
          <span>
            {t('lifecycle.similarity.matchedBy')}:{' '}
            {match.matched_fields
              .map((field) => t(`lifecycle.newPrompt.similar.methods.${field}`, { defaultValue: field }))
              .join(' · ')}
          </span>
        ) : null}
        {/* A cosine or nothing. A lexical-only row has no vector score, and
            inventing one — the old dialog rendered a term-overlap ratio as
            "100% similar" — is how a prompt nobody had indexed came to look
            like a certain duplicate. */}
        <span>
          {typeof match?.similarity === 'number'
            ? t('lifecycle.similarity.cosine', { percent: percent(match.similarity) })
            : t('lifecycle.similarity.noCosine')}
        </span>
        {overlap && overlap.metadata_overlap > 0 ? (
          <span>
            {t('lifecycle.similarity.sharedMetadata', { percent: percent(overlap.metadata_overlap) })}
          </span>
        ) : null}
      </section>
    </div>
  );
}

/** The two prompts side by side, aligned block by block where both are canonical.
 *
 * Aligning matters more than it looks: an `instructions` block read against
 * another prompt's `system` block is the same category error as embedding a
 * whole document, made by a person instead of by a model. When either side has
 * not been converted to canonical XML yet — the import screen's normal case —
 * this falls back to whole text against whole text and says so by simply having
 * one row. */
function BlockComparison({ sourceText, existingText }: { sourceText: string; existingText: string }) {
  const { t } = useTranslation();

  const pairs = useMemo(() => {
    const incoming = parseXmlBlocks(sourceText);
    const existing = parseXmlBlocks(existingText);
    if (!incoming.success || !existing.success) {
      return [{ tag: null, incoming: sourceText, existing: existingText }];
    }
    const byTag = new Map(existing.blocks.map((block) => [block.tag, block.content]));
    const shared = incoming.blocks.filter((block) => byTag.has(block.tag));
    if (shared.length === 0) {
      return [{ tag: null, incoming: sourceText, existing: existingText }];
    }
    return shared.map((block) => ({
      tag: block.tag,
      incoming: block.content,
      existing: byTag.get(block.tag) ?? '',
    }));
  }, [sourceText, existingText]);

  return (
    <div className="grid gap-3">
      {pairs.map((pair, index) => {
        const shared = sharedWordsOf(pair.existing, pair.incoming);
        return (
          <div key={pair.tag ?? `pair-${index}`} className="grid gap-2">
            {pair.tag ? <code className="text-caption font-semibold text-ink">{pair.tag}</code> : null}
            <div className="grid gap-3 lg:grid-cols-2">
              <section className="rounded-xl border border-border bg-surface p-3">
                <h5 className="mb-2 text-caption font-semibold text-muted">
                  {t('lifecycle.newPrompt.similar.incomingComparison')}
                </h5>
                <WordHeatmap text={pair.incoming} sharedWords={shared} className="max-h-52 overflow-auto text-caption" />
              </section>
              <section className="rounded-xl border border-border bg-surface p-3">
                <h5 className="mb-2 text-caption font-semibold text-muted">
                  {t('lifecycle.newPrompt.similar.existingComparison')}
                </h5>
                <WordHeatmap text={pair.existing} sharedWords={shared} className="max-h-52 overflow-auto text-caption" />
              </section>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/**
 * Choose between revising a match and creating a prompt, from the evidence.
 *
 * **The default is "create a new prompt", and that is the fix rather than a
 * detail.** This dialog used to pre-select `matches[0]`, so a false positive
 * made the path of least resistance *attach an incoming prompt as a revision of
 * an unrelated one*. It now pre-selects whatever the backend recommends, which
 * is an existing prompt only when exactly one candidate was judged to do the
 * same job with no breaking contract change — and is otherwise a new prompt,
 * the outcome that discards nothing and writes something recoverable.
 *
 * **And it shows its working.** A verdict on its own is an assertion a reader
 * can only accept: the panel below carries which blocks overlapped, on which
 * words, which variables both prompts read, which retrieval legs fired, and the
 * reason codes behind the judgement. A row here is an accusation that this
 * prompt might be the one you already have, so a reader has to be able to look
 * at it and say *no* — three unrelated prompts were being shown as duplicates
 * precisely because nothing on the screen could be contradicted.
 */
export function SimilarPromptsDialog({
  open,
  reviewOnly = false,
  matches,
  candidates = [],
  coverage = [],
  recommendedTarget,
  retrieved,
  adjudicated,
  matchFloor = 0,
  belowFloor = 0,
  sourceText,
  onContinue,
  onStop,
}: SimilarPromptsDialogProps) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<string>(NEW_PROMPT);

  const evidence = useMemo(
    () => new Map(candidates.map((candidate) => [candidate.prompt_id, candidate])),
    [candidates],
  );

  useEffect(() => {
    if (open) setSelected(reviewOnly ? matches[0]?.prompt_id ?? NEW_PROMPT : recommendedTarget ?? NEW_PROMPT);
  }, [open, recommendedTarget, reviewOnly, matches]);

  const selectedMatch = matches.find((match) => match.prompt_id === selected);
  const selectedEvidence = selectedMatch ? evidence.get(selectedMatch.prompt_id) : undefined;
  const existingText = selectedMatch?.body_preview ?? selectedMatch?.purpose ?? '';

  return (
    <Modal
      open={open}
      title={t('lifecycle.newPrompt.similar.aiTitle')}
      description={<Trans i18nKey="lifecycle.newPrompt.similar.aiSubtitle" components={{ strong: <strong /> }} />}
      icon={<Sparkle className="size-5" weight="fill" />}
      confirmLabel={t(reviewOnly ? 'common.close' : 'lifecycle.newPrompt.similar.continue')}
      showCancel={!reviewOnly}
      onClose={onStop}
      onConfirm={() => onContinue(reviewOnly || selected === NEW_PROMPT ? undefined : selected)}
      size="wide"
    >
      <div className="grid gap-4">
        <fieldset className="grid gap-2">
          <legend className="sr-only">{t(reviewOnly ? 'lifecycle.newPrompt.similar.reviewLegend' : 'lifecycle.newPrompt.similar.legend')}</legend>
          {matches.map((match) => {
            const candidate = evidence.get(match.prompt_id);
            return (
              <div
                key={match.prompt_id}
                className={cn(
                  'rounded-lg border border-border p-3',
                  selected === match.prompt_id ? 'border-primary bg-subtle' : null,
                )}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Radio
                    name="prope-similar-target"
                    value={match.prompt_id}
                    checked={selected === match.prompt_id}
                    onChange={() => setSelected(match.prompt_id)}
                    label={t(reviewOnly ? 'lifecycle.newPrompt.similar.comparePrompt' : 'lifecycle.newPrompt.similar.asNewVersion', { title: match.title })}
                  />
                  {candidate ? (
                    <Tag state={candidate.verdict === 'same' ? 'success' : 'neutral'}>
                      {t(`lifecycle.similarity.verdict.${candidate.verdict}`)}
                    </Tag>
                  ) : null}
                  {candidate && !candidate.adjudicated ? (
                    <Tag state="neutral">{t('lifecycle.similarity.unadjudicated')}</Tag>
                  ) : null}
                </div>

                {candidate ? (
                  <p className="mt-1 text-caption leading-relaxed text-muted">
                    {t(`lifecycle.similarity.verdictHint.${candidate.verdict}`)}
                  </p>
                ) : null}

                {/* On every row rather than only the selected one: these five
                    are what the choice between the rows is made on, and a
                    reader comparing two candidates should not have to select
                    each in turn to see the numbers. */}
                {candidate ? <MetricGrid candidate={candidate} match={match} /> : null}

                {candidate && candidate.findings.length > 0 ? (
                  <ul className="mt-2 grid gap-1.5">
                    {candidate.findings.map((finding, index) => (
                      <FindingRow key={`${finding.code}-${index}`} finding={finding} />
                    ))}
                  </ul>
                ) : null}
              </div>
            );
          })}

          {reviewOnly ? null : <div
            className={cn(
              'rounded-lg border border-border p-3',
              selected === NEW_PROMPT ? 'border-primary bg-subtle' : null,
            )}
          >
            <Radio
              name="prope-similar-target"
              value={NEW_PROMPT}
              checked={selected === NEW_PROMPT}
              onChange={() => setSelected(NEW_PROMPT)}
              label={t('lifecycle.newPrompt.similar.createNew')}
            />
            <p className="mt-1 text-caption leading-relaxed text-muted">
              {t('lifecycle.newPrompt.similar.createNewHint')}
            </p>
          </div>}
        </fieldset>

        {selectedMatch && selectedEvidence ? (
          <section className="rounded-xl border border-border bg-subtle p-4">
            <h3 className="mb-3 text-body font-semibold text-ink">{t('lifecycle.similarity.howTitle')}</h3>
            <HowSimilar
              candidate={selectedEvidence}
              match={selectedMatch}
              overlap={selectedEvidence.overlap}
            />
          </section>
        ) : null}

        {selectedMatch ? <BlockComparison sourceText={sourceText} existingText={existingText} /> : null}

        <section className="rounded-xl border border-border bg-subtle p-4">
          <h3 className="text-body font-semibold text-ink">{t('lifecycle.similarity.evidenceTitle')}</h3>
          <p className="mt-1 text-caption leading-relaxed text-muted">
            {selectedEvidence
              ? t(`lifecycle.similarity.verdictHint.${selectedEvidence.verdict}`)
              : t('lifecycle.similarity.noVerdict')}
          </p>
          {typeof retrieved === 'number' ? (
            <p className="mt-1 text-caption text-muted">
              {t('lifecycle.similarity.funnel', {
                retrieved,
                adjudicated: adjudicated ?? 0,
                shown: matches.length,
              })}
              {matchFloor > 0 ? (
                <> {t('lifecycle.similarity.floorNote', { floor: percent(matchFloor) })}</>
              ) : null}
              {belowFloor > 0 ? (
                <> {t('lifecycle.similarity.floorHidden', { hidden: belowFloor, floor: percent(matchFloor) })}</>
              ) : null}
            </p>
          ) : null}
          {coverage.length > 0 ? (
            <ul className="mt-3 grid gap-1.5">
              {coverage.map((finding, index) => (
                <FindingRow key={`${finding.code}-${index}`} finding={finding} />
              ))}
            </ul>
          ) : null}
        </section>
      </div>
    </Modal>
  );
}
