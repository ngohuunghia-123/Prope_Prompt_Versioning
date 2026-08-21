import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Notification } from '@/components/Notification';
import {
  PROMPT_DRAFTS_CHANGED,
  clearPromptDraft,
  promptDraftKey,
  readPromptDraft,
  type StoredPromptDraft,
} from '@/features/prompt-lifecycle/promptDraftStorage';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';

/**
 * "You left a prompt half-written in this folder."
 *
 * The composer restores its own draft on the way in, but only somebody who
 * thinks to open the composer again ever finds out. This is the other half:
 * the folder is where a person goes looking for the prompt they thought they
 * had made, and a draft that nothing surfaces is a draft nobody knows to
 * resume.
 *
 * Reads storage rather than a query, because that is where the draft is —
 * nothing about it exists server-side. It listens for the composer's own
 * change event as well as `storage`: `storage` fires only in OTHER tabs, so
 * without the local event a draft saved and then discarded in this tab would
 * leave the notice up.
 */
export function PromptDraftResumeNotice({ folderId }: { folderId: string }) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const navigate = useNavigate();
  const key = promptDraftKey(folderId);
  const [draft, setDraft] = useState<StoredPromptDraft>();

  const refresh = useCallback(() => setDraft(readPromptDraft(key)), [key]);

  useEffect(() => {
    refresh();
    window.addEventListener(PROMPT_DRAFTS_CHANGED, refresh);
    window.addEventListener('storage', refresh);
    return () => {
      window.removeEventListener(PROMPT_DRAFTS_CHANGED, refresh);
      window.removeEventListener('storage', refresh);
    };
  }, [refresh]);

  if (!draft) return null;

  return (
    <Notification tone="info" title={t('lifecycle.folders.detail.draft.title')}>
      <span>
        {t('lifecycle.folders.detail.draft.body', {
          title: draft.title || t('lifecycle.newPrompt.untitled'),
          at: format.date(draft.savedAt),
        })}{' '}
        <button
          type="button"
          className="cursor-pointer font-semibold text-link underline"
          onClick={() => void navigate(`/app/prompts/folder/${encodeURIComponent(folderId)}/new`)}
        >
          {t('lifecycle.folders.detail.draft.resume')}
        </button>
        {' · '}
        <button
          type="button"
          className="cursor-pointer font-semibold text-link underline"
          onClick={() => { clearPromptDraft(key); refresh(); }}
        >
          {t('lifecycle.folders.detail.draft.discard')}
        </button>
      </span>
    </Notification>
  );
}
