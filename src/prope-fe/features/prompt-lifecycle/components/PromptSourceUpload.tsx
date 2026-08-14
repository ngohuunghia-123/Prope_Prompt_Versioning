import { FileArrowUp, FileText, X } from '@phosphor-icons/react';
import { useId, useRef, useState, type ChangeEvent, type DragEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';
import { Button } from '@/components/ui/Button';
import { MAX_SOURCE_CHARACTERS, type PromptSourceFormat } from '@/features/prompt-lifecycle/types';

export interface PromptSourceFile {
  text: string;
  format: PromptSourceFormat;
  filename: string;
}

export interface PromptSourceUploadProps {
  filename?: string;
  disabled?: boolean;
  onLoad: (file: PromptSourceFile) => void;
  onClear: () => void;
}

const ACCEPT = '.txt,.md,.markdown,.json,.yaml,.yml,.xml';

// Extension → the `source_format` the conversion endpoint understands. Anything
// unrecognised is `txt`, which is the honest answer rather than a refusal: the
// converter reads prose either way, and a person who named their prompt
// `refund-v2.prompt` should not be told their file is the wrong kind.
const FORMAT_BY_EXTENSION: Record<string, PromptSourceFormat> = {
  md: 'markdown',
  markdown: 'markdown',
  json: 'json',
  yaml: 'yaml',
  yml: 'yaml',
  xml: 'xml',
  txt: 'txt',
};

function formatOf(filename: string): PromptSourceFormat {
  const extension = filename.split('.').pop()?.toLowerCase() ?? '';
  return FORMAT_BY_EXTENSION[extension] ?? 'txt';
}

export function PromptSourceUpload({ filename, disabled = false, onLoad, onClear }: PromptSourceUploadProps) {
  const { t } = useTranslation();
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string>();
  const [dragging, setDragging] = useState(false);

  // Read here rather than at submit time. The size limit is the server's, and a
  // file that cannot be saved should say so while the person is still looking at
  // the upload row — not after they have filled in the rest of the form.
  const accept = async (file: File | undefined) => {
    if (!file) return;
    setError(undefined);
    const text = await file.text();
    if (!text.trim()) {
      setError(t('lifecycle.newPrompt.source.uploadEmpty'));
      return;
    }
    if (text.length > MAX_SOURCE_CHARACTERS) {
      setError(t('lifecycle.newPrompt.source.uploadTooLarge'));
      return;
    }
    onLoad({ text, format: formatOf(file.name), filename: file.name });
  };

  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    void accept(event.target.files?.[0]);
    // Cleared so re-picking the same file after a clear still fires `change`.
    event.target.value = '';
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    if (disabled) return;
    void accept(event.dataTransfer.files?.[0]);
  };

  if (filename) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-subtle p-4">
        <span className="flex min-w-0 items-center gap-2 text-body text-ink">
          <FileText aria-hidden className="size-5 shrink-0 text-muted" />
          <span className="truncate font-medium">{filename}</span>
        </span>
        <Button type="button" intent="neutral" size="small" leadingIcon={<X aria-hidden className="size-4" />} onClick={onClear}>
          {t('lifecycle.newPrompt.source.clear')}
        </Button>
      </div>
    );
  }

  return (
    <div className="grid gap-2">
      <div
        onDragOver={(event) => { event.preventDefault(); if (!disabled) setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={cn(
          'flex flex-col items-center gap-2 rounded-xl border border-dashed border-border p-6 text-center transition-colors',
          dragging && 'border-focus bg-accent-soft',
          disabled && 'opacity-50',
        )}
      >
        <FileArrowUp aria-hidden className="size-6 text-muted" />
        <label htmlFor={inputId} className="text-body font-medium text-ink">
          {t('lifecycle.newPrompt.source.uploadLabel')}
        </label>
        <p className="text-caption text-muted">{t('lifecycle.newPrompt.source.uploadHint')}</p>
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          accept={ACCEPT}
          disabled={disabled}
          onChange={handleChange}
          className="sr-only"
        />
        <Button type="button" intent="neutral" size="small" disabled={disabled} onClick={() => inputRef.current?.click()}>
          {t('lifecycle.newPrompt.source.uploadAction')}
        </Button>
      </div>
      {error ? <p role="alert" className="text-caption text-danger-text">{error}</p> : null}
    </div>
  );
}
