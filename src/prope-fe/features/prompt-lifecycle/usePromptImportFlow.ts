import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFindSimilarPromptsMutation, useImportPromptMutation } from '@/features/prompt-lifecycle/queries';
import type { PromptEditorValues, PromptSearchResult } from '@/features/prompt-lifecycle/types';

/** Where the import has got to. Only one dialog is ever open.
 *
 * `idle` between runs, `similar` while the near-match dialog is up, `convert`
 * while the XML question is up, `saving` while the writes are in flight. The
 * state is what the screen renders from, so a dialog cannot be open for a run
 * that has already moved on.
 */
export type ImportStage = 'idle' | 'similar' | 'convert' | 'saving';

/** `undefined` means "create a new prompt"; a string is the prompt to add a
 * revision to. Kept beside the stage rather than inside it so that choosing a
 * target in the first dialog survives into the second. */
type Target = string | undefined;

export interface PromptImportFlow {
  stage: ImportStage;
  matches: PromptSearchResult[];
  /** True once the similarity request has failed; the flow continues anyway. */
  similarityFailed: boolean;
  importFailed: boolean;
  /** Whether the XML question is worth asking for the values in hand. */
  start: (values: PromptEditorValues) => Promise<void>;
  chooseTarget: (target: Target) => void;
  cancel: () => void;
  finish: (convert: boolean) => void;
}

export function usePromptImportFlow(): PromptImportFlow {
  const navigate = useNavigate();
  const similarity = useFindSimilarPromptsMutation();
  const importMutation = useImportPromptMutation();

  const [stage, setStage] = useState<ImportStage>('idle');
  const [matches, setMatches] = useState<PromptSearchResult[]>([]);
  const [values, setValues] = useState<PromptEditorValues>();
  const [target, setTarget] = useState<Target>();

  // Already-canonical XML has nothing to convert, so the question would be a
  // dialog with one real answer. Skipping it is not a shortcut: it is the
  // difference between asking something and asking something meaningless.
  const needsConversion = (candidate: PromptEditorValues) =>
    candidate.sourceMode === 'existing' && candidate.sourceFormat !== 'xml';

  const persist = (candidate: PromptEditorValues, chosen: Target, convert: boolean) => {
    setStage('saving');
    importMutation.mutate(
      { values: candidate, targetPromptId: chosen, convert },
      {
        onSuccess: (result) => {
          setStage('idle');
          void navigate(`/app/prompts/${result.promptId}`);
        },
        onError: () => setStage('idle'),
      },
    );
  };

  const advance = (candidate: PromptEditorValues, chosen: Target) => {
    if (needsConversion(candidate)) {
      setStage('convert');
      return;
    }
    persist(candidate, chosen, false);
  };

  const start = async (candidate: PromptEditorValues) => {
    setValues(candidate);
    setTarget(undefined);
    importMutation.reset();

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
  };

  const finish = (convert: boolean) => {
    if (!values) return;
    persist(values, target, convert);
  };

  return {
    stage,
    matches,
    similarityFailed: similarity.isError,
    importFailed: importMutation.isError,
    start,
    chooseTarget,
    cancel,
    finish,
  };
}
