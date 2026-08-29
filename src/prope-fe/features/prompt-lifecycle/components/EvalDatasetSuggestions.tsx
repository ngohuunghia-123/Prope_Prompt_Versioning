import { Sparkle } from '@phosphor-icons/react';
import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Notification } from '@/components/Notification';
import { useSuggestEvalDatasetsMutation } from '@/features/prompt-lifecycle/queries';

interface EvalDatasetSuggestionsProps {
  promptId: string;
  versionId: string;
  /** Sets already attached, so a proposal for one of them reads as confirmed. */
  attached: Set<string>;
  disabled: boolean;
  onAttach: (datasetId: string) => void;
  /** The container the popover spans: the workspace row that holds the dataset
   * panel and the run console. Without it the popover falls back to the width
   * of its own trigger. */
  containerRef?: RefObject<HTMLDivElement | null>;
}

interface PopoverPosition {
  top: number;
  left: number;
  width: number;
}

/** The advisor's "which sets should measure this prompt?" trigger and answer.
 *
 * A proposal is advice, never a write: attaching one runs the same tick the
 * tree uses, so a suggestion cannot change the yardstick by itself. Reasons
 * come from the library's own metadata, which is what makes them judgeable at
 * a glance — the person reads one sentence and decides.
 *
 * The answer opens in a popover instead of filling the workspace: a catalogue
 * of proposals pushes the datasets the person is trying to reach below the
 * fold, while a proposal list is read once and dismissed. The panel renders
 * through a portal and spans the whole workspace row — wider than the tree
 * column it is triggered from, so the reasons and their attach buttons get the
 * room the outer container has. */
export function EvalDatasetSuggestions({ promptId, versionId, attached, disabled, onAttach, containerRef }: EvalDatasetSuggestionsProps) {
  const { t } = useTranslation();
  const suggest = useSuggestEvalDatasetsMutation(promptId);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<PopoverPosition>();
  const triggerRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const measure = useCallback((): PopoverPosition | undefined => {
    const trigger = triggerRef.current?.getBoundingClientRect();
    if (!trigger) return undefined;
    // Wide against the workspace row when the caller can point at it; otherwise
    // hugging the trigger itself is still better than a fixed guess.
    const container = containerRef?.current?.getBoundingClientRect() ?? trigger;
    return { top: trigger.bottom + 8, left: container.left, width: container.width };
  }, [containerRef]);

  // The popover is light-weight on purpose — one anchored panel, closed by
  // clicking anywhere else or pressing Escape. That is the whole interaction;
  // a focus-trapped dialog would be heavier than the content it holds.
  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: PointerEvent) {
      const target = event.target as Node;
      if (!triggerRef.current?.contains(target) && !panelRef.current?.contains(target)) setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false);
    }
    // Capture phase, so scrolling inside the panel's own scroll area does not
    // drag the anchor out from under it while any container scrolls.
    function onScroll() {
      setPosition(measure());
    }
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    window.addEventListener('scroll', onScroll, true);
    window.addEventListener('resize', onScroll);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('scroll', onScroll, true);
      window.removeEventListener('resize', onScroll);
    };
  }, [open, measure]);

  const hasResults = suggest.data !== undefined;
  function toggle() {
    if (open) {
      setOpen(false);
      return;
    }
    setPosition(measure());
    setOpen(true);
    if (!hasResults) suggest.mutate({ versionId });
  }

  return (
    <div ref={triggerRef}>
      <Button
        type="button"
        intent="neutral"
        className="w-full"
        aria-expanded={open}
        loading={suggest.isPending}
        disabled={disabled}
        leadingIcon={<Sparkle aria-hidden weight="fill" className="size-4" />}
        onClick={toggle}
      >
        {t('lifecycle.evalAdvisor.suggest')}
      </Button>
      {open && position
        ? createPortal(
            <div
              ref={panelRef}
              role="dialog"
              aria-label={t('lifecycle.evalAdvisor.suggest')}
              style={{ top: position.top, left: position.left, width: position.width }}
              className="fixed z-30 rounded-modal border border-border bg-surface p-4 shadow-panel"
            >
              <p className="text-caption text-muted">{t('lifecycle.evalAdvisor.suggestHint')}</p>
              {suggest.isError ? (
                <div className="mt-3">
                  <Notification tone="error" title={t('lifecycle.evalAdvisor.suggestError')}>
                    {t('lifecycle.evalAdvisor.suggestErrorHint')}
                  </Notification>
                </div>
              ) : null}
              {suggest.isPending ? (
                <p className="mt-3 text-caption text-muted">{t('lifecycle.evalAdvisor.suggestLoading')}</p>
              ) : null}
              {suggest.data ? (
                suggest.data.suggestions.length === 0 ? (
                  <p className="mt-3 rounded-control bg-subtle p-3 text-caption text-muted">{t('lifecycle.evalAdvisor.none')}</p>
                ) : (
                  <ul className="mt-3 grid max-h-72 gap-2 overflow-y-auto">
                    {suggest.data.suggestions.map((suggestion) => {
                      const isAttached = attached.has(suggestion.dataset_id);
                      return (
                        <li key={suggestion.dataset_id} className="rounded-control border border-border bg-surface p-3">
                          <div className="flex flex-wrap items-start justify-between gap-2">
                            <div className="grid min-w-0 gap-1">
                              <p className="text-body font-semibold text-ink">{suggestion.name}</p>
                              <p className="text-caption text-muted">{suggestion.reason}</p>
                            </div>
                            <div className="flex shrink-0 items-center gap-2">
                              <span className="text-caption text-muted">
                                {t('lifecycle.evalAdvisor.confidence', { percent: Math.round(suggestion.confidence * 100) })}
                              </span>
                              {isAttached ? (
                                <span className="text-caption font-semibold text-success-text">{t('lifecycle.evalAdvisor.attached')}</span>
                              ) : (
                                <Button type="button" intent="neutral" size="small" onClick={() => onAttach(suggestion.dataset_id)}>
                                  {t('lifecycle.evalAdvisor.attach')}
                                </Button>
                              )}
                            </div>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                )
              ) : null}
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}
