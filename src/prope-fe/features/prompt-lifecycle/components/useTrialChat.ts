import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  runTrial,
  type TrialParameters,
  type TrialTurn,
  type TrialUsage,
} from '@/features/prompt-lifecycle/trialApi';
import { isApiError } from '@/lib/apiClient';

export interface Turn extends TrialTurn {
  /** Set while the assistant turn is still being streamed into. */
  pending?: boolean;
}

/** What the settings panel currently has set. Empty strings mean "as the revision binds". */
export interface TrialSettings {
  providerConfigId: string;
  upstreamModel: string;
  parameters: TrialParameters;
}

/** The running meter. Every figure here is *this session's*, not the workspace's. */
export interface TrialTotals {
  turns: number;
  inputTokens: number;
  outputTokens: number;
  /** Summed from the priced turns only. `null` when no turn in the session was priced. */
  cost: number | null;
  currency: string | null;
  /** Turns whose `(provider, model)` pair has no price row. Counted, never treated as free. */
  unpricedTurns: number;
}

const EMPTY_TOTALS: TrialTotals = {
  turns: 0,
  inputTokens: 0,
  outputTokens: 0,
  cost: null,
  currency: null,
  unpricedTurns: 0,
};

/**
 * One playground conversation: the thread, the stream, and the meter.
 *
 * **The thread lives here and nowhere else.** No server state, no cache entry, no
 * `localStorage`: a reload clears it. That is deliberate rather than unfinished —
 * a playground thread is scratch work whose turns can contain anything somebody
 * pasted in to see what happens, and the moment it is persisted it acquires a
 * retention question, an access question, and a row in somebody's audit. What
 * *is* recorded is the call itself, in the ledger, under `source='playground'`,
 * which is the accounting fact rather than the conversation.
 *
 * **Every send posts the whole thread.** The trial endpoint holds no
 * conversation, so context is whatever this hook sends — which also makes
 * "delete the last exchange and try again" work with no server involvement.
 *
 * **The totals are a session counter and not an invoice.** Each turn's own cost
 * is the server's ten-place `Decimal`, kept verbatim as a string; the running sum
 * below is float arithmetic over those strings, for a number on a screen that is
 * being read to the nearest fraction of a cent. The ledger's totals are the
 * figures that count, and they are computed from the rows rather than from this.
 */
export function useTrialChat(options: {
  promptId: string;
  versionId: string;
  variables: Record<string, string>;
  settings: TrialSettings;
}) {
  const { promptId, versionId, variables, settings } = options;
  const { t } = useTranslation();

  const [turns, setTurns] = useState<Turn[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string>();
  const [lastUsage, setLastUsage] = useState<TrialUsage>();
  const [totals, setTotals] = useState<TrialTotals>(EMPTY_TOTALS);
  /** Characters received on the turn in flight — the only figure that can move live. */
  const [received, setReceived] = useState(0);

  const abortRef = useRef<AbortController>(null);
  // The send closure reads these at call time rather than through the dependency
  // array: a settings change mid-stream must not re-create the sender and orphan
  // the controller the abort path holds.
  const latest = useRef({ variables, settings });
  latest.current = { variables, settings };

  // Abandon an in-flight read when the panel goes away. The server-side call is
  // not cancelled and its ledger row is still written — the provider generated
  // those tokens and somebody is paying for them.
  useEffect(() => () => abortRef.current?.abort(), []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setTurns([]);
    setError(undefined);
    setStreaming(false);
    setLastUsage(undefined);
    setTotals(EMPTY_TOTALS);
    setReceived(0);
  }, []);

  const send = useCallback(
    async (thread: TrialTurn[]) => {
      const controller = new AbortController();
      abortRef.current = controller;
      const { variables: currentVariables, settings: currentSettings } = latest.current;

      setStreaming(true);
      setError(undefined);
      setReceived(0);
      setLastUsage(undefined);
      setTurns([...thread, { role: 'assistant', content: '', pending: true }]);

      try {
        await runTrial(
          promptId,
          versionId,
          {
            messages: thread,
            variables: currentVariables,
            ...(currentSettings.providerConfigId && currentSettings.upstreamModel
              ? {
                  providerConfigId: currentSettings.providerConfigId,
                  upstreamModel: currentSettings.upstreamModel,
                }
              : {}),
            parameters: currentSettings.parameters,
          },
          {
            onDelta: (text) => {
              setReceived((current) => current + text.length);
              setTurns((current) => {
                const next = [...current];
                const last = next.at(-1);
                if (last?.pending) next[next.length - 1] = { ...last, content: last.content + text };
                return next;
              });
            },
            onUsage: (usage) => {
              setLastUsage(usage);
              setTotals((current) => {
                const turnCost = usage.cost === null ? null : Number(usage.cost);
                return {
                  turns: current.turns + 1,
                  inputTokens: current.inputTokens + (usage.inputTokens ?? 0),
                  outputTokens: current.outputTokens + (usage.outputTokens ?? 0),
                  cost:
                    turnCost === null || Number.isNaN(turnCost)
                      ? current.cost
                      : (current.cost ?? 0) + turnCost,
                  currency: usage.currency ?? current.currency,
                  unpricedTurns: current.unpricedTurns + (usage.cost === null ? 1 : 0),
                };
              });
            },
            onError: (failure) => {
              setError(
                t(`lifecycle.playground.dispatchError.${failure.errorClass}`, {
                  defaultValue: t('lifecycle.playground.dispatchError.unknown'),
                }),
              );
            },
          },
          controller.signal,
        );
      } catch (thrown) {
        if (controller.signal.aborted) return;
        // The server's machine `code`, translated here (ADR-0053) — the envelope's
        // `message` is English and is for a log, never for a screen.
        setError(
          isApiError(thrown)
            ? t(`lifecycle.playground.refusal.${thrown.code}`, {
                defaultValue: t('lifecycle.states.error.description'),
              })
            : t('lifecycle.states.error.description'),
        );
      } finally {
        if (!controller.signal.aborted) {
          setStreaming(false);
          // Drop a pending turn that never received a delta — an empty bubble
          // beside an error message reads as an answer that was blank rather than
          // an answer that never came.
          setTurns((current) => {
            const last = current.at(-1);
            if (last?.pending && last.content === '') return current.slice(0, -1);
            return current.map((turn) => (turn.pending ? { ...turn, pending: false } : turn));
          });
        }
      }
    },
    [promptId, t, versionId],
  );

  const submit = useCallback(
    (content: string) => {
      const text = content.trim();
      if (!text || streaming) return;
      void send([
        ...turns.map(({ role, content: existing }) => ({ role, content: existing })),
        { role: 'user', content: text },
      ]);
    },
    [send, streaming, turns],
  );

  const retry = useCallback(() => {
    // Everything up to and including the last user turn, which is what the
    // failed attempt was answering. Walked by index rather than with
    // `findLastIndex`: the tsconfig targets a lib that predates it.
    let lastUser = -1;
    for (let index = turns.length - 1; index >= 0; index -= 1) {
      if (turns[index]?.role === 'user') {
        lastUser = index;
        break;
      }
    }
    if (lastUser === -1) return;
    void send(turns.slice(0, lastUser + 1).map(({ role, content }) => ({ role, content })));
  }, [send, turns]);

  return { turns, streaming, error, lastUsage, totals, received, submit, retry, reset };
}
