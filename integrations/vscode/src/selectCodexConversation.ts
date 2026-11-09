import * as vscode from 'vscode';
import { z } from 'zod';
import { conversationIdSchema } from '@connector/contracts';
import { ConnectorError } from './api';
import { readCodexMetadata } from './codexThreadTitle';

const pageSchema = z.object({ data: z.array(z.object({ id: conversationIdSchema, name: z.string().max(1000).nullable().optional() })).max(50), nextCursor: z.string().max(4000).nullable().optional() });
export const listCodexConversations = (binary: string, cwd: string, cursor?: string) => {
  // VS Code lowercases drive letters; Codex may have stored the uppercase form.
  const project = /^[a-z]:[\\/]/i.test(cwd) ? [...new Set([cwd, cwd.slice(0, 1).toUpperCase() + cwd.slice(1), cwd.slice(0, 1).toLowerCase() + cwd.slice(1)])] : cwd;
  return readCodexMetadata(binary, 'thread/list', {
    cwd: project, limit: 50, sourceKinds: ['vscode', 'cli', 'appServer'], sortKey: 'updated_at', sortDirection: 'desc', useStateDbOnly: true, ...(cursor ? { cursor } : {}),
  }, (raw) => pageSchema.parse(raw));
};

export async function selectCodexConversation(binary: string, cwd: string) {
  const t = vscode.l10n.t; let cursor: string | undefined;
  const seen = new Set<string>();
  for (let page = 0; page < 10; page += 1) {
    const result = await listCodexConversations(binary, cwd, cursor);
    if (!result.data.length) { await vscode.window.showInformationMessage(t('No Codex conversations found in this VS Code project.')); return; }
    const items = result.data.map((thread) => ({
      label: thread.name?.trim() ? thread.name.replace(/[$\p{Cc}\p{Cf}]/gu, '') : t('Untitled conversation'),
      description: thread.id, id: thread.id,
    }));
    if (result.nextCursor && page < 9 && !seen.has(result.nextCursor)) items.push({ label: t('Load older conversations'), description: '', id: '' });
    const chosen = await vscode.window.showQuickPick(items, { placeHolder: t('Choose a Codex conversation in this project. This does not identify the active chat tab.') });
    if (!chosen) return;
    if (chosen.id) return chosen.id;
    cursor = result.nextCursor ?? undefined;
    if (!cursor) return;
    if (seen.has(cursor)) throw new ConnectorError('codex_list_invalid_cursor');
    seen.add(cursor);
  }
}
