import type { UseFormReturn } from 'react-hook-form';
import { MAX_SOURCE_CHARACTERS, type PromptEditorValues, type PromptSourceFormat } from '@/features/prompt-lifecycle/types';

export interface PromptSourceFile {
  text: string;
  format: PromptSourceFormat;
  filename: string;
}

/** The two ways a file is refused, as catalogue keys under `newPrompt.source`. */
export type PromptSourceFileError = 'uploadEmpty' | 'uploadTooLarge';

export const PROMPT_SOURCE_ACCEPT = '.txt,.md,.markdown,.json,.yaml,.yml,.xml';

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

export function formatOfFilename(filename: string): PromptSourceFormat {
  const extension = filename.split('.').pop()?.toLowerCase() ?? '';
  return FORMAT_BY_EXTENSION[extension] ?? 'txt';
}

/**
 * Read a picked file, or say why it cannot be used.
 *
 * Read at pick time rather than at submit time. The size limit is the server's
 * (`MAX_CANONICAL_CHARACTERS`), and a file that cannot be saved should say so
 * while the person is still looking at the Import bar — not after they have
 * filled in the rest of the form and pressed the button.
 */
export async function readPromptSourceFile(file: File): Promise<PromptSourceFile | PromptSourceFileError> {
  const text = await file.text();
  if (!text.trim()) return 'uploadEmpty';
  if (text.length > MAX_SOURCE_CHARACTERS) return 'uploadTooLarge';
  return { text, format: formatOfFilename(file.name), filename: file.name };
}

/**
 * Put the form back to having no imported source.
 *
 * Both the Import bar and the body panel offer this, so it is written once:
 * three fields plus the mode have to move together, and a clear that forgot
 * `sourceMode` would leave the body panel showing an empty source view.
 */
export function clearPromptSource(form: UseFormReturn<PromptEditorValues>): void {
  form.setValue('sourceText', '', { shouldDirty: true });
  form.setValue('sourceFilename', undefined, { shouldDirty: true });
  form.setValue('sourceFormat', 'txt', { shouldDirty: true });
  form.setValue('sourceMode', 'authored', { shouldDirty: true, shouldValidate: true });
}
