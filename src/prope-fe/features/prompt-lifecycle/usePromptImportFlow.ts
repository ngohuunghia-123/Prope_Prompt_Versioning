import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AUTHORED_PROVENANCE, type SourceProvenance } from '@/features/prompt-lifecycle/api';
import {
  useFindSimilarPromptsMutation,
  useImportPromptMutation,
  useResolvePromptSourceMutation,
} from '@/features/prompt-lifecycle/queries';
import type { PromptEditorValues, PromptSearchResult } from '@/features/prompt-lifecycle/types';

/** Where the import has got to. Only one dialog is ever open.
 *
 * `idle` between runs, `checking` while the duplicate check is in flight,
 * `similar` while the near-match dialog is up, `convert` while the XML question
 * is up, `converting` while the converter is working, `review` while the
 * converted blocks are on screen waiting to be read, `saving` while the writes
 * are in flight. `checking` earns its place: the embedding call behind it has
 * been measured at up to 25 seconds, and without a stage of its own the button
 * stayed enabled the whole time and a second press started a second import. The
 * state is what the screen renders from, so a dialog cannot be open for a run
 * that has already moved on.
 *
 * `review` is the one stage with no request in flight and no dialog. A revision
 * is immutable once written (A-021), so a conversion that goes straight to the
 * database is a conversion whose mistakes cost a second revision to undo. The
 * blocks land in the editor and the flow waits for the user to evaluate them.
 */
export type ImportStage = 'idle' | 'checking' | 'similar' | 'convert' | 'converting' | 'review' | 'saving';

/** `undefined` means "create a new prompt"; a string is the prompt to add a
 * revision to. Kept beside the stage rather than inside it so that choosing a
 * target in the first dialog survives into the second. */
type Target = string | undefined;

export interface PromptImportFlow {
  stage: ImportStage;
  matches: PromptSearchResult[];
  /** True once the similarity request has failed; the flow continues anyway. */
  similarityFailed: boolean;
  conversionFailed: boolean;
  importFailed: boolean;
  start: (values: PromptEditorValues) => Promise<void>;
  chooseTarget: (target: Target) => void;
  cancel: () => void;
  /** Answers the XML question and puts the resolved prompt into the editor. */
  finish: (convert: boolean) => void;
  /** Persists the reviewed body and advances to evaluation. */
  continueAfterReview: (values: PromptEditorValues) => void;
}

export interface PromptImportFlowOptions {
  /** Writes the canonical body into the form so the editor can show it. */
  onConverted: (body: string) => void;
}

export function usePromptImportFlow({ onConverted }: PromptImportFlowOptions): PromptImportFlow {
  const navigate = useNavigate();
  const similarity = useFindSimilarPromptsMutation();
  const resolveSource = useResolvePromptSourceMutation();
  const importMutation = useImportPromptMutation();

  const [stage, setStage] = useState<ImportStage>('idle');
  const [matches, setMatches] = useState<PromptSearchResult[]>([]);
  const [values, setValues] = useState<PromptEditorValues>();
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
          // The button says "Đánh giá", and until step 4 it landed on the
          // prompt detail page — which is where the flow went to die, because
          // nothing there asks what should measure the prompt. The revision
          // travels in the URL rather than in router state so a refresh on the
          // eval page keeps evaluating the revision that was just written.
          void navigate(
            `/app/prompts/${result.promptId}/evaluation/run?version=${encodeURIComponent(result.versionId)}`,
          );
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
  };

  const start = async (candidate: PromptEditorValues) => {
    setValues(candidate);
    setTarget(undefined);
    resolveSource.reset();
    importMutation.reset();
    setStage('checking');

    const text = candidate.sourceMode === 'existing' ? candidate.sourceText : candidate.promptBody;
    let found: PromptSearchResult[] = [];
    try {
      const response = await similarity.mutateAsync(text);
      found = response.prompts;
    } catch {
      // A duplicate check is advice, not a gate. The workspace may have nothing
      // indexed, the embedding service may be down — neither is a reason to
      // refuse somebody their own prompt. The failure is surfaced on the next
      // screen state rather than swallowed silently.
      found = [];
    }

    setMatches(found);
    if (found.length === 0) {
      advance(candidate, undefined);
      return;
    }
    setStage('similar');
  };

  const chooseTarget = (chosen: Target) => {
    if (!values) return;
    setTarget(chosen);
    advance(values, chosen);
  };

  const cancel = () => {
    setStage('idle');
    setMatches([]);
    setProvenance(undefined);
  };

  const finish = (convert: boolean) => {
    if (!values) return;
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
    similarityFailed: similarity.isError,
    conversionFailed: resolveSource.isError,
    importFailed: importMutation.isError,
    start,
    chooseTarget,
    cancel,
    finish,
    continueAfterReview,
  };
}
