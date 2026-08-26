import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
<<<<<<< Updated upstream
import { AUTHORED_PROVENANCE, type SourceProvenance } from '@/features/prompt-lifecycle/api';
import { clearLastProviderBinding, rememberProviderBinding } from '@/features/prompt-lifecycle/providerBindingMemory';
import { clearLastRouterCombo, rememberRouterCombo } from '@/features/prompt-lifecycle/routerComboMemory';
import {
  useFindSimilarPromptsMutation,
  useImportPromptMutation,
  useResolvePromptSourceMutation,
} from '@/features/prompt-lifecycle/queries';
import type {
  ComparisonCandidate,
  ComparisonFinding,
  PromptEditorValues,
  PromptSearchResult,
  SimilarityStep,
} from '@/features/prompt-lifecycle/types';

/** Where the import has got to. Only one dialog is ever open.
 *
 * `idle` between runs, `checking` while the duplicate check is in flight,
 * `trace` once it has finished and had nothing to ask about, `similar` while the
 * near-match dialog is up, `convert` while the XML question is up, `converting`
 * while the converter is working, `review` while the converted blocks are on
 * screen waiting to be read, `saving` while the writes are in flight. `checking`
 * earns its place: the embedding call behind it has been measured at up to 25
 * seconds, and without a stage of its own the button stayed enabled the whole
 * time and a second press started a second import. The state is what the screen
 * renders from, so a dialog cannot be open for a run that has already moved on.
 *
 * **`trace` is the stage the match floor created.** Only a candidate covering
 * 90% of the incoming prompt is listed, so *nothing to show* is now the ordinary
 * outcome — and a check that runs for twenty seconds and then vanishes has told
 * nobody anything. Here the run's own trace stays on screen with its counts
 * ("checked 18, one under 90%") and the person closes it. Like `similar` and
 * `convert` it waits on somebody rather than on a request.
 *
 * `review` is the one stage with no request in flight and no dialog. A revision
 * is immutable once written (A-021), so a conversion that goes straight to the
 * database is a conversion whose mistakes cost a second revision to undo. The
 * blocks land in the editor and the flow waits for the user to evaluate them.
 */
export type ImportStage =
  | 'idle'
  | 'checking'
  | 'trace'
  | 'similar'
  | 'convert'
  | 'converting'
  | 'review'
  | 'saving';

/** `undefined` means "create a new prompt"; a string is the prompt to add a
 * revision to. Kept beside the stage rather than inside it so that choosing a
 * target in the first dialog survives into the second. */
=======
import { DETERMINISTIC_WRAP_MODEL, DETERMINISTIC_WRAP_SCHEMA_VERSION, wrapAsInstructions } from '@/features/prompt-lifecycle/api';
import { useConvertPromptSourceMutation, useFindSimilarPromptsMutation, useImportPromptMutation } from '@/features/prompt-lifecycle/queries';
import type { ConversionSourceFormat, PromptEditorValues, PromptSearchResult } from '@/features/prompt-lifecycle/types';

export type ImportStage = 'idle' | 'checking' | 'similar' | 'convert' | 'converting' | 'saving';
>>>>>>> Stashed changes
type Target = string | undefined;

export interface ConversionProvenance {
  originalFormat: ConversionSourceFormat;
  originalBody: string;
  originalFilename?: string;
  conversionModel: string;
  conversionSchemaVersion: string;
}

export interface PromptImportFlow {
  stage: ImportStage;
  matches: PromptSearchResult[];
<<<<<<< Updated upstream
  /** One classification per row of `matches`, joined by `prompt_id`. */
  candidates: ComparisonCandidate[];
  /** What the dialog should PRE-SELECT. `undefined` means "create a new
   * prompt", which is the default whenever the evidence for anything else is
   * incomplete — it discards nothing and writes something recoverable. */
  recommendedTarget: Target;
  /** Findings about the answer itself: adjudication unavailable, how much of
   * the workspace is indexed. An empty `matches` means "nothing indexed
   * resembles this" and never "this is not a duplicate", and this is what
   * carries the difference. */
  coverage: ComparisonFinding[];
  /** How wide the funnel was: how many prompts retrieval offered, and how many
   * reached the adjudicator. What was CHECKED, which is a larger number than
   * what is listed and is the honest way to say so. */
  retrieved: number;
  adjudicated: number;
  /** The floor a candidate had to clear to be listed, and how many cleared
   * everything else and were held back by it. */
  matchFloor: number;
  belowFloor: number;
  /** Every rung the funnel has reported so far, in the order it reported them.
   * The bottom sheet is a view of this array and nothing else. */
  steps: SimilarityStep[];
  /** Whether the trace sheet is on screen. Open from the press of the button;
   * closed once a dialog takes over, or by the person. */
  traceOpen: boolean;
  /** Closes the sheet and — when the check found nothing to ask about — lets
   * the import carry on. */
  dismissTrace: () => void;
  /** Puts the last run's trace back on screen. Reads what already happened and
   * starts nothing: re-running the check would cost another twenty-five seconds
   * and another adjudication call to answer a question that has been answered.
   * The steps survive until the next press of "Đánh giá". */
  reopenTrace: () => void;
  /** True once the similarity request has failed; the flow continues anyway. */
=======
>>>>>>> Stashed changes
  similarityFailed: boolean;
  conversionFailed: boolean;
  importFailed: boolean;
<<<<<<< Updated upstream
=======
  conversionFailed: boolean;
>>>>>>> Stashed changes
  start: (values: PromptEditorValues) => Promise<void>;
  chooseTarget: (target: Target) => void;
  cancel: () => void;
  /** Answers the XML question and puts the resolved prompt into the editor. */
  finish: (convert: boolean) => void;
  /** Persists the reviewed body and advances to evaluation. */
  continueAfterReview: (values: PromptEditorValues) => void;
}

<<<<<<< Updated upstream
export interface PromptImportFlowOptions {
  /** Writes the canonical body into the form so the editor can show it. */
  onConverted: (body: string) => void;
  /** Editing always appends to this prompt and never asks duplicate-selection. */
  targetPromptId?: string;
  /** The revision is written and the screen is about to leave. Called before
   * the navigation so the recovery draft is dropped in the same turn the thing
   * it was protecting stopped being at risk — a draft left behind here is the
   * one that would be offered back on a folder whose prompt already exists. */
  onSaved?: () => void;
  evaluationSearch?: string;
}

export function usePromptImportFlow({ onConverted, targetPromptId, onSaved, evaluationSearch }: PromptImportFlowOptions): PromptImportFlow {
=======
export function usePromptImportFlow(onConverted: (values: PromptEditorValues, provenance: ConversionProvenance) => void): PromptImportFlow {
>>>>>>> Stashed changes
  const navigate = useNavigate();
  const similarity = useFindSimilarPromptsMutation();
  const resolveSource = useResolvePromptSourceMutation();
  const importMutation = useImportPromptMutation();
  const conversionMutation = useConvertPromptSourceMutation();
  const [stage, setStage] = useState<ImportStage>('idle');
  const [matches, setMatches] = useState<PromptSearchResult[]>([]);
  const [candidates, setCandidates] = useState<ComparisonCandidate[]>([]);
  const [coverage, setCoverage] = useState<ComparisonFinding[]>([]);
  const [recommendedTarget, setRecommendedTarget] = useState<Target>();
  const [funnel, setFunnel] = useState({ retrieved: 0, adjudicated: 0, matchFloor: 0, belowFloor: 0 });
  const [steps, setSteps] = useState<SimilarityStep[]>([]);
  const [traceOpen, setTraceOpen] = useState(false);
  const [values, setValues] = useState<PromptEditorValues>();
<<<<<<< Updated upstream
  const [target, setTarget] = useState<Target>();
  const [provenance, setProvenance] = useState<SourceProvenance>();

  // An imported source is raw text until something turns it into blocks. A body
  // already in the editor — authored there, or an `.xml` file the Import panel
  // put there directly — has nothing to convert, so the question would be a
  // dialog with one real answer.
  const needsConversion = (candidate: PromptEditorValues) => candidate.sourceMode === 'existing';

  /**
   * `onFailure` is where a failed write leaves the screen, and it is not always
   * `idle`. A save that failed after a conversion must come back to `review`:
   * the provenance the revision needs — `original_body`, `conversion_model` —
   * lives in this hook's state, and `idle` would put the button back to "Đánh
   * giá", whose next press starts a fresh run against a form that now looks
   * authored. The retry would succeed and quietly record the converted XML as
   * hand-written.
   */
  const persist = (
    candidate: PromptEditorValues,
    chosen: Target,
    recorded: SourceProvenance,
    onFailure: ImportStage,
  ) => {
    setStage('saving');
    importMutation.mutate(
      { values: candidate, targetPromptId: chosen, provenance: recorded },
      {
        onSuccess: (result) => {
          setStage('idle');
          onSaved?.();
          // Offered back as the default on the next prompt this browser
          // composes. Here rather than in the selects, because "last used" has
          // to mean a revision was written with it — a provider somebody picked
          // and then reconsidered is not what they use.
          //
          // Two keys, and the loser is CLEARED (ADR-0069): whichever memory
          // survives is the mode, so leaving a stale one behind would offer a
          // combo to somebody whose last save was a pair. The cross-clear lives
          // here rather than inside either memory module, or the two would have
          // to import each other for a rule that belongs to whoever knows which
          // mode was saved.
          //
          // `else if` and not a bare `else`: `rememberProviderBinding` is
          // already a no-op on an empty binding, so a bare `else` would clear
          // the combo memory on an UNBOUND save while writing nothing — a
          // behaviour change from today for a case that means "no opinion".
          if (candidate.bindingMode === 'combo' && candidate.routeComboId) {
            rememberRouterCombo(candidate.routeComboId);
            clearLastProviderBinding();
          } else if (candidate.providerConfigId && candidate.upstreamModel) {
            rememberProviderBinding(candidate);
            clearLastRouterCombo();
          }
          // The button says "Đánh giá", and until step 4 it landed on the
          // prompt detail page — which is where the flow went to die, because
          // nothing there asks what should measure the prompt. The revision
          // travels in the URL rather than in router state so a refresh on the
          // eval page keeps evaluating the revision that was just written.
          const nextParams = new URLSearchParams(evaluationSearch);
          // Step navigation carries the revision that was opened. A real save
          // is the one place that value must move forward, so replace it with
          // the immutable revision the write just created rather than appending
          // a second `version` parameter or leaving the old one in place.
          nextParams.set('version', result.versionId);
          void navigate(`/app/prompts/${result.promptId}/evaluation/run?${nextParams.toString()}`);
        },
        onError: () => setStage(onFailure),
      },
    );
  };

  const advance = (candidate: PromptEditorValues, chosen: Target) => {
    if (needsConversion(candidate)) {
      setStage('convert');
      return;
    }
    // Nothing was converted, so there is no review to fall back to.
    persist(candidate, chosen, AUTHORED_PROVENANCE, 'idle');
=======
  const [provenance, setProvenance] = useState<ConversionProvenance>();

  const needsConversion = (candidate: PromptEditorValues) => candidate.sourceMode === 'existing' && candidate.sourceFormat !== 'xml';
  const persist = (candidate: PromptEditorValues, targetPromptId?: string) => {
    setStage('saving');
    importMutation.mutate({ values: candidate, targetPromptId, provenance }, {
      onSuccess: (result) => {
        setStage('idle');
        void navigate(`/app/prompts/${result.promptId}/edit`, { state: { guidedValidation: true } });
      },
      onError: () => setStage('idle'),
    });
>>>>>>> Stashed changes
  };

  const start = async (candidate: PromptEditorValues) => {
    setValues(candidate);
<<<<<<< Updated upstream
    setTarget(targetPromptId);
    resolveSource.reset();
    importMutation.reset();
    if (targetPromptId) {
      advance(candidate, targetPromptId);
      return;
    }
    setSteps([]);
    // Up from the press of the button, not from the first event: the sheet's job
    // is to account for the wait, and the first rung can take several seconds to
    // report because retrieval has to embed the body first.
    setTraceOpen(true);
    setStage('checking');

    const text = candidate.sourceMode === 'existing' ? candidate.sourceText : candidate.promptBody;
    let found: PromptSearchResult[] = [];
    try {
      const response = await similarity.mutateAsync({
        text,
        onStep: (step) => setSteps((previous) => [...previous, step]),
      });
      found = response.prompts;
      setCandidates(response.candidates);
      setCoverage(response.coverage);
      setFunnel({
        retrieved: response.retrieved,
        adjudicated: response.adjudicated,
        matchFloor: response.match_floor,
        belowFloor: response.below_floor,
      });
      // `recommended_prompt_id` is only ever set alongside `add_revision`, and
      // the backend sets that only when exactly one candidate was judged to do
      // the same job with no breaking contract change. Everything else — an
      // unavailable adjudicator, two equally-same candidates, any hard finding —
      // arrives here as `undefined` and pre-selects "create a new prompt".
      setRecommendedTarget(
        response.recommended_action === 'add_revision'
          ? (response.recommended_prompt_id ?? undefined)
          : undefined,
      );
    } catch {
      // A duplicate check is advice, not a gate. The workspace may have nothing
      // indexed, the embedding service may be down — neither is a reason to
      // refuse somebody their own prompt. The failure is surfaced on the next
      // screen state rather than swallowed silently.
      found = [];
      setCandidates([]);
      setCoverage([]);
      setFunnel({ retrieved: 0, adjudicated: 0, matchFloor: 0, belowFloor: 0 });
      setRecommendedTarget(undefined);
    }

    setMatches(found);
    if (found.length === 0) {
      // Nothing to ask about, so the trace becomes the answer rather than
      // disappearing with it. At a 90% floor this is the ordinary outcome, and
      // "checked 18, nothing over 90%" is a different statement from silence.
      setStage('trace');
      return;
    }
    setTraceOpen(false);
    setStage('similar');
  };

  /** Close the sheet. From `trace` that also means "carry on with the import",
   * because the sheet is the only thing the flow is waiting on. */
  const dismissTrace = () => {
    setTraceOpen(false);
    if (stage === 'trace' && values) advance(values, undefined);
  };

  const reopenTrace = () => {
    if (steps.length > 0) setTraceOpen(true);
  };

  const chooseTarget = (chosen: Target) => {
    if (!values) return;
    setTarget(chosen);
    advance(values, chosen);
  };

  const cancel = () => {
    setStage('idle');
    setMatches([]);
    setCandidates([]);
    setCoverage([]);
    setFunnel({ retrieved: 0, adjudicated: 0, matchFloor: 0, belowFloor: 0 });
    setRecommendedTarget(undefined);
    setProvenance(undefined);
    setTraceOpen(false);
    setSteps([]);
=======
    importMutation.reset();
    conversionMutation.reset();
    if (needsConversion(candidate)) {
      setStage('convert');
      return;
    }
    setStage('checking');
    let found: PromptSearchResult[] = [];
    try { found = (await similarity.mutateAsync(candidate.promptBody)).prompts; } catch { found = []; }
    setMatches(found);
    if (found.length === 0) persist(candidate);
    else setStage('similar');
>>>>>>> Stashed changes
  };

  const chooseTarget = (targetPromptId?: string) => { if (values) persist(values, targetPromptId); };
  const cancel = () => { setStage('idle'); setMatches([]); };
  const finish = (convert: boolean) => {
    if (!values) return;
<<<<<<< Updated upstream
    setStage('converting');
    resolveSource.mutate(
      { values, targetPromptId: target, convert },
      {
        onSuccess: (resolved) => {
          onConverted(resolved.body);
          setValues({ ...values, promptBody: resolved.body, sourceMode: 'authored' });
          setProvenance(resolved.provenance);
          setStage('review');
        },
        // Back to the form with the source still loaded, so the answer to a
        // converter that is down is to press the button again.
        onError: () => setStage('idle'),
      },
    );
  };

  const continueAfterReview = (reviewedValues: PromptEditorValues) => {
    if (stage !== 'review' || !provenance) return;
    persist(reviewedValues, target, provenance, 'review');
  };

  return {
    stage,
    matches,
    candidates,
    coverage,
    recommendedTarget,
    retrieved: funnel.retrieved,
    adjudicated: funnel.adjudicated,
    matchFloor: funnel.matchFloor,
    belowFloor: funnel.belowFloor,
    steps,
    traceOpen,
    dismissTrace,
    reopenTrace,
    similarityFailed: similarity.isError,
    conversionFailed: resolveSource.isError,
    importFailed: importMutation.isError,
    start,
    chooseTarget,
    cancel,
    finish,
    continueAfterReview,
  };
=======
    const originalFormat = values.sourceFormat as ConversionSourceFormat;
    const apply = (xmlBody: string, conversionModel: string, conversionSchemaVersion: string) => {
      const convertedValues = { ...values, sourceMode: 'authored' as const, promptBody: xmlBody };
      const conversionProvenance = { originalFormat, originalBody: values.sourceText, originalFilename: values.sourceFilename, conversionModel, conversionSchemaVersion };
      setProvenance(conversionProvenance);
      onConverted(convertedValues, conversionProvenance);
      setStage('idle');
    };
    if (!convert) {
      apply(wrapAsInstructions(values.sourceText), DETERMINISTIC_WRAP_MODEL, DETERMINISTIC_WRAP_SCHEMA_VERSION);
      return;
    }
    setStage('converting');
    conversionMutation.mutate(
      { sourceText: values.sourceText, sourceFormat: originalFormat },
      { onSuccess: (result) => apply(result.xml_body, result.model, result.schema_version), onError: () => setStage('idle') },
    );
  };

  return { stage, matches, similarityFailed: similarity.isError, importFailed: importMutation.isError, conversionFailed: conversionMutation.isError, start, chooseTarget, cancel, finish };
>>>>>>> Stashed changes
}
