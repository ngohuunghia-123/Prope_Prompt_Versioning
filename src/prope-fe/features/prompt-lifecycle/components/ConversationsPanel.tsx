import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Drawer } from '@/components/ui/Drawer';
import { ConversationGraphView } from '@/features/prompt-lifecycle/components/ConversationGraphView';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import {
  conversationGraphOptions,
  promptConversationsOptions,
} from '@/features/prompt-lifecycle/queries';
import type { ConversationSummary } from '@/features/prompt-lifecycle/insightsTypes';

/**
 * The end-user conversations this prompt took part in, and one of them as a graph.
 *
 * **Sits above the call list because it is the same rows, grouped.** A log line
 * says *this prompt answered at 14:03*; a conversation says *this prompt was the
 * second of four steps in a chat that ended badly*. The second question is the
 * one somebody debugging an application actually has, and it is unanswerable
 * from a flat list no matter how long you stare at it.
 *
 * **Empty is the ordinary state and is explained, not rendered as a blank
 * table.** Nothing in an OpenAI-compatible request identifies a conversation, so
 * a customer has none of these until their application starts sending
 * `prope.conversation_id` — which is one line in their client. The empty copy
 * says exactly that, because a reader who thinks the feature is broken will not
 * go and add the line.
 */
export function ConversationsPanel({ promptId }: { promptId: string }) {
  const { t } = useTranslation();
  const [openId, setOpenId] = useState<string | null>(null);

  const list = useQuery(promptConversationsOptions(promptId, null, null));
  const graph = useQuery({
    ...conversationGraphOptions(promptId, openId ?? ''),
    enabled: openId !== null,
  });

  return (
    <section aria-labelledby="conversations-title" className="border-b border-border bg-surface">
      <header className="px-4 py-4 sm:px-5">
        <p className="text-overline font-bold tracking-navigation-overline text-secondary uppercase">
          {t('lifecycle.insights.conversations.eyebrow')}
        </p>
        <h3 id="conversations-title" className="mt-1 font-display text-heading-3 text-ink">
          {t('lifecycle.insights.conversations.title')}
        </h3>
        <p className="mt-1 text-caption text-muted">
          {t('lifecycle.insights.conversations.description')}
        </p>
      </header>

      {list.isPending ? (
        <QueryState state="loading" loadingLayout="table" />
      ) : list.isError ? (
        <QueryState state="error" onRetry={() => void list.refetch()} />
      ) : list.data?.length ? (
        <ul className="m-0 grid list-none gap-px border-t border-border bg-border p-0">
          {list.data.map((conversation) => (
            <ConversationRow
              key={conversation.conversation_id}
              conversation={conversation}
              onOpen={() => setOpenId(conversation.conversation_id)}
            />
          ))}
        </ul>
      ) : (
        <p className="border-t border-border px-4 py-8 text-center text-body text-muted sm:px-5">
          {t('lifecycle.insights.conversations.empty')}
        </p>
      )}

      <Drawer
        open={openId !== null}
        onClose={() => setOpenId(null)}
        side="right"
        size="full"
        title={t('lifecycle.insights.conversations.graphTitle')}
      >
        {graph.isPending ? (
          <QueryState state="loading" loadingLayout="table" />
        ) : graph.isError ? (
          <QueryState state="error" onRetry={() => void graph.refetch()} />
        ) : graph.data ? (
          <ConversationGraphView graph={graph.data} />
        ) : null}
      </Drawer>
    </section>
  );
}

function ConversationRow({
  conversation,
  onOpen,
}: {
  conversation: ConversationSummary;
  onOpen: () => void;
}) {
  const { t, i18n } = useTranslation();
  const when = new Date(conversation.last_called_at).toLocaleString(i18n.language);

  return (
    <li className="bg-surface">
      <button
        type="button"
        onClick={onOpen}
        className="grid w-full grid-cols-[minmax(0,1fr)_auto] items-baseline gap-3 border-0 bg-transparent px-4 py-3 text-left hover:bg-canvas focus-visible:outline-2 focus-visible:outline-focus sm:px-5"
      >
        <span className="grid gap-0.5">
          <span className="truncate font-mono text-caption text-ink">
            {conversation.conversation_id}
          </span>
          <span className="text-overline text-muted">
            {t('lifecycle.insights.conversations.steps', { count: conversation.call_count })}
            {' · '}
            {t('lifecycle.insights.conversations.prompts', { count: conversation.prompt_count })}
            {conversation.error_count > 0
              ? ` · ${t('lifecycle.insights.conversations.errors', { count: conversation.error_count })}`
              : ''}
          </span>
        </span>
        <span className="shrink-0 text-overline tabular-nums text-muted">{when}</span>
      </button>
    </li>
  );
}
