import { useCallback, useRef, useState, type ChangeEvent, type ClipboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import type { AttachmentFormat } from '@/features/chat/types';

/** A paste longer than this is a prompt body, not a sentence. */
const PASTE_ATTACH_THRESHOLD = 1_000;
/** The server refuses attachments past this ceiling; refuse them here instead. */
const MAX_ATTACHMENT_CHARACTERS = 32_768;

const ACCEPT = '.txt,.md,.markdown,.json,.yaml,.yml';
const FORMAT_BY_EXTENSION: Partial<Record<string, AttachmentFormat>> = {
  txt: 'txt', md: 'md', markdown: 'markdown', json: 'json', yaml: 'yaml', yml: 'yaml',
};

/**
 * Everything the composer needs to carry a whole prompt body.
 *
 * Two ways in, one rule: the body travels as the attachment, never inside the
 * message — a 4 KB prompt in the message field is what the server's guardrail
 * layer would have to inspect as if it were a question, and what the import
 * tools could never reach. A paste longer than the threshold is intercepted
 * before it lands in the textarea; files are read as text and typed by
 * extension, mirroring the formats the wire accepts.
 */
export function useChatAttachment(attach: (text: string, format: AttachmentFormat) => void) {
  const { t } = useTranslation();
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const addText = useCallback((text: string, format: AttachmentFormat) => {
    if (!text.trim()) return false;
    if (text.length > MAX_ATTACHMENT_CHARACTERS) {
      setError(t('chat.attachment.tooLarge'));
      return true;
    }
    setError(null);
    attach(text, format);
    return true;
  }, [attach, t]);

  /** Returns true when the paste became an attachment and must not also land in the textarea. */
  const handlePaste = useCallback((event: ClipboardEvent<HTMLTextAreaElement>) => {
    const text = event.clipboardData.getData('text/plain');
    if (text.length < PASTE_ATTACH_THRESHOLD) return false;
    event.preventDefault();
    return addText(text, 'txt');
  }, [addText]);

  const openPicker = useCallback(() => fileInputRef.current?.click(), []);

  const handleFile = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    const extension = file.name.split('.').pop()?.toLowerCase() ?? '';
    const format = FORMAT_BY_EXTENSION[extension];
    if (!format) {
      setError(t('chat.attachment.unsupported'));
      return;
    }
    void file.text()
      .then((content) => { addText(content, format); })
      .catch(() => setError(t('chat.attachment.unsupported')));
  }, [addText, t]);

  return { error, clearError: useCallback(() => setError(null), []), handlePaste, openPicker, handleFile, fileInputRef, accept: ACCEPT };
}
