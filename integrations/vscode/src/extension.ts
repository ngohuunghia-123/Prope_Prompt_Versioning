import * as vscode from 'vscode';
import { createHash, randomUUID } from 'node:crypto';
import { mkdir, writeFile, unlink } from 'node:fs/promises';
import { z } from 'zod';
import { ManagementApi, ConnectorError } from './api';
import { Broker } from './broker';
import { Proposals } from './proposals';
import { Panel } from './panel';
import { allowedRead } from './readPolicy';
import { agentCheckSchema, conversationTitleTargetSchema, evaluationProposalSchema } from '@connector/contracts';
import { PANEL_OWNER } from '@connector/directContracts';
import { DirectActions } from './directActions';
import { readCodexThreadTitle } from './codexThreadTitle';
import { readCodexSession } from './codexSession';
import { SessionChat } from './sessionChat';
import { sessionChatRequestSchema } from '@connector/sessionChatContracts';
import { selectChatBinding } from './selectChatBinding';
import { selectCodexConversation } from './selectCodexConversation';

const t = vscode.l10n.t;
export async function activate(context: vscode.ExtensionContext) {
  if (vscode.env.remoteName) throw new Error(t('Prope v1 requires a local VS Code window.'));
  const output = vscode.window.createOutputChannel('Prope', { log: true });
  const api = new ManagementApi(context.secrets, vscode.workspace.getConfiguration('prope').get<string>('backendUrl', 'http://127.0.0.1:8080'), (event) => output.info(JSON.stringify(event)));
  await api.restore();
  const proposals = new Proposals(api); const broker = new Broker(api, proposals);
  await broker.start();
  const windowId = createHash('sha256').update(vscode.workspace.workspaceFolders?.[0]?.uri.toString() ?? 'empty').digest('hex').slice(0, 16);
  await mkdir(context.globalStorageUri.fsPath, { recursive: true });
  const endpoint = vscode.Uri.joinPath(context.globalStorageUri, `endpoint-${windowId}.json`);
  await writeFile(endpoint.fsPath, JSON.stringify({ port: broker.port }), { mode: 0o600 });
  const confirm = async (message: string) => await vscode.window.showWarningMessage(message, { modal: true }, t('Confirm')) === t('Confirm');
  const codexBinary = () => {
    const configured = vscode.workspace.getConfiguration('chatgpt').get<string | null>('cliExecutable');
    const codex = vscode.extensions.getExtension('openai.chatgpt');
    if (!configured && (!codex || process.platform !== 'win32' || process.arch !== 'x64')) throw new ConnectorError('codex_title_unavailable');
    return configured || (codex ? vscode.Uri.joinPath(codex.extensionUri, 'bin/windows-x86_64/codex.exe').fsPath : '');
  };
  const sessionChat = new SessionChat(api, broker, (id) => readCodexSession(codexBinary(), id), (operation, id, binding) => confirm(operation === 'grant'
    ? t('Allow Prope to read user messages and final answers in Codex thread {0}? Only refresh on your request. Messages may contain sensitive data. No system prompts or tool results are shared.', id)
    : operation === 'send'
      ? t('Send relevant excerpts from the selected session to PropAI for this question? This uses Prope providers and may incur costs. Previously sent data cannot be recalled. Thread: {0}', id)
      : binding ? t('Save the displayed prompt with provider {0}, model {1}, thread {2}? No release changes.', binding.provider_config_id, binding.upstream_model, id)
        : t('Apply this displayed PropAI decision? It may save a prompt revision or start a paid evaluation. Thread: {0}', id)), () => selectChatBinding(api));
  const direct = new DirectActions(api, proposals, (operation) => confirm(operation === 'run'
    ? t('Run this revision on all attached datasets? This incurs provider costs.')
    : t('Improve this revision using the selected evaluation evidence? This uses Prope providers and may incur evaluation costs.')));
  const panel = new Panel(context, async (action, payload) => {
    if (action === 'connect') return connect();
    if (action === 'disconnect') return disconnect();
    if (action === 'pair') return pair();
    if (action === 'configuration') return configuration();
    if (action === 'agent_connections') return broker.connections();
    if (action === 'check_agent') return broker.check(agentCheckSchema.parse(payload).connection_id);
    if (action === 'choose_conversation') {
      const input = agentCheckSchema.parse(payload);
      return broker.chooseConversation(input.connection_id, async () => {
        const folder = vscode.workspace.workspaceFolders?.[0];
        if (!folder || folder.uri.scheme !== 'file') throw new ConnectorError('codex_workspace_required');
        return selectCodexConversation(codexBinary(), folder.uri.fsPath);
      });
    }
    if (action === 'session_chat') {
      const requestId = randomUUID(); const started = performance.now(); let status = 'error';
      const input = sessionChatRequestSchema.safeParse(payload);
      try { const result = await sessionChat.execute(payload); status = 'success'; return result; }
      catch (error) { throw new ConnectorError(error instanceof ConnectorError ? error.code : 'invalid_response', error instanceof ConnectorError ? error.status : 400, requestId); }
      finally { output.info(JSON.stringify({ event: 'connector.session_chat', request_id: requestId, operation: input.success ? input.data.operation : 'invalid', status, latency_ms: Math.round(performance.now() - started) })); }
    }
    if (action === 'conversation_title') {
      const input = conversationTitleTargetSchema.parse(payload); const requestId = randomUUID(); const started = performance.now();
      let status = 'error';
      try {
        const result = await broker.conversationTitle(input.connection_id, input.thread_id, async (id) => {
          return readCodexThreadTitle(codexBinary(), id);
        });
        status = 'success'; return result;
      } catch (error) { throw new ConnectorError(error instanceof ConnectorError ? error.code : 'codex_title_unavailable', error instanceof ConnectorError ? error.status : 400, requestId); }
      finally { output.info(JSON.stringify({ event: 'connector.thread_title', request_id: requestId, connection_id: input.connection_id, status, latency_ms: Math.round(performance.now() - started) })); }
    }
    if (['capture_direct', 'stage_revision', 'stage_comparison', 'attach_datasets', 'create_dataset', 'run_revision', 'start_improvement', 'review_improvement'].includes(action)) return direct.execute(action, payload);
    if (action === 'manage') {
      const target = z.object({ prompt_id: z.string().regex(/^[a-zA-Z0-9_:@.-]+$/).optional() }).strict().parse(payload);
      return vscode.env.openExternal(vscode.Uri.parse(`${api.baseUrl.replace(/\/$/, '')}${target.prompt_id ? `/app/prompts/${encodeURIComponent(target.prompt_id)}?tab=evaluation` : '/app/settings/providers'}`));
    }
    if (action === 'state') {
      const session = await api.session().catch((error: unknown) => { if (error instanceof ConnectorError && error.status === 401) return null; throw error; });
      return { connected: Boolean(session?.user.workspace_id), workspace_id: session?.user.workspace_id ?? null, workspace_name: session?.user.workspace_name ?? null, proposals: proposals.list() };
    }
    await api.session();
    if (action === 'read') return api.request(allowedRead(payload));
    const data = z.object({ proposal_id: z.string(), destination: z.unknown().optional(), digest: z.string().optional(), evaluation: z.unknown().optional() }).strict().parse(payload);
    const proposal = proposals.get(data.proposal_id);
    if (action === 'reject') { proposals.discard(proposal.id); return null; }
    const namespace = proposal.connection_id === PANEL_OWNER ? proposal.namespace : broker.namespace(proposal.connection_id);
    if (!namespace) throw new ConnectorError('pair_expired');
    if (action === 'stage_evaluation') {
      const input = evaluationProposalSchema.parse(data.evaluation);
      const prompt = await api.prompt(input.prompt_id);
      if (prompt.namespace !== namespace) throw new ConnectorError('scope_denied', 403);
      return proposals.addEvaluation(proposal.connection_id, { kind: 'evaluation', ...input }, namespace);
    }
    if (action === 'preview') {
      const target = z.object({ namespace: z.string() }).passthrough().parse(data.destination);
      if (target.namespace !== namespace) throw new ConnectorError('scope_denied', 403);
      if (proposal.input.kind !== 'evaluation' && proposal.input.format !== 'xml' && !await confirm(t('Convert this prompt using the configured provider? This may incur a cost.'))) throw new ConnectorError('cancelled');
      return proposals.preview(proposal.id, data.destination);
    }
    if (action === 'save') {
      if (!await confirm(t('Save the exact preview as a new Prope revision? No release will be changed.'))) throw new ConnectorError('cancelled');
      return proposals.save(proposal.id, data.digest ?? '');
    }
    if (action === 'evaluate' && proposal.input.kind === 'evaluation' && proposal.status === 'pending') {
      const input = proposal.input; const prompt = await api.prompt(input.prompt_id);
      if (prompt.namespace !== namespace) throw new ConnectorError('scope_denied', 403);
      return proposals.evaluate(proposal.id, () => confirm(t('Run both selected revisions on the same dataset? This incurs provider costs.')));
    }
    throw new ConnectorError('action_denied', 403);
  }, () => { sessionChat.clear(); direct.clear(); proposals.clear(); });
  proposals.changed = () => panel.changed(); broker.open = () => { void panel.open(); };
  api.onInvalidated = () => { sessionChat.clear(); direct.clear(); broker.revoke(); panel.changed(true); };
  async function connect() {
    const email = await vscode.window.showInputBox({ prompt: t('Prope account email'), ignoreFocusOut: true }); if (!email) return;
    const password = await vscode.window.showInputBox({ prompt: t('Prope password (not saved)'), password: true, ignoreFocusOut: true }); if (!password) return;
    await api.clear();
    await api.request('/api/v1/auth/login', 'POST', { email, password });
    const session = await api.session();
    if (session.must_change_password) { await vscode.env.openExternal(vscode.Uri.parse(`${api.baseUrl.replace(/\/$/, '')}/change-password`)); throw new ConnectorError('password_change_required'); }
    const list = z.object({ items: z.array(z.object({ workspace_id: z.string(), name: z.string(), status: z.string() })) }).parse(await api.request('/api/v1/auth/workspaces'));
    const selected = await vscode.window.showQuickPick(list.items.filter((item) => item.status === 'active').map((item) => ({ label: item.name, id: item.workspace_id })), { placeHolder: t('Choose a Prope workspace') });
    if (selected) await api.request(`/api/v1/auth/workspaces/${encodeURIComponent(selected.id)}/enter`, 'POST');
    panel.changed(true);
  }
  async function pair() {
    const pending = broker.pending();
    if (!pending.length) { await vscode.window.showInformationMessage(t('No waiting MCP clients. Configure Prope MCP in your host and restart its MCP connection, then try pairing again. No chat message is needed.')); return; }
    const safeLabel = (value: string) => value.replace(/[$\p{Cc}\p{Cf}]/gu, '').slice(0, 100);
    const selected = await vscode.window.showQuickPick(pending.map((item) => ({
      label: t('MCP client: {0}', item.client ? safeLabel(item.client.name) : t('Unknown client')),
      description: t('Connection {0}', item.code), detail: t('Client details are self-reported. Version: {0}. Observed MCP thread IDs: {1}', item.client ? safeLabel(item.client.version) : t('Unknown client'), [...(item.conversations?.keys() ?? [])].join(', ') || t('No thread ID observed')), code: item.code,
    })), { placeHolder: t('Choose the waiting MCP client to pair') });
    if (!selected) return;
    const folders = z.array(z.object({ slug: z.string(), name: z.string() })).parse(await api.request('/api/v1/folders'));
    const folder = await vscode.window.showQuickPick(folders.map((item) => ({ label: item.name, description: item.slug })), { placeHolder: t('Allow this agent to read prompt bodies in this folder') });
    if (!folder) return;
    if (!await confirm(t('Allow {0} ({1}) to read prompt content in folder {2} and send proposals? The client name is self-reported.', selected.label, selected.code, folder.label))) return;
    await broker.approve(selected.code, folder.description); panel.changed();
    void vscode.window.showInformationMessage(t('Access granted for {0} in folder {1}. The adapter will connect within a few seconds.', selected.label, folder.label));
  }
  async function disconnect() {
    try { await api.request('/api/v1/auth/logout', 'POST'); } finally { await api.clear(); panel.changed(); }
  }
  async function configuration() {
    const args = [vscode.Uri.joinPath(context.extensionUri, 'dist/mcp-stdio.mjs').fsPath, '--endpoint', endpoint.fsPath];
    const document = await vscode.workspace.openTextDocument({ language: 'json', content: JSON.stringify({
      claude_mcp_config: { mcpServers: { prope: { command: 'node', args } } },
      codex_config_toml: `[mcp_servers.prope]\ncommand = "node"\nargs = ${JSON.stringify(args)}\n`,
    }, null, 2) });
    await vscode.window.showTextDocument(document, vscode.ViewColumn.Beside);
  }
  const commands: Record<string, () => Promise<unknown>> = { open: () => panel.open(), connect, pair, disconnect, configuration };
  for (const [name, handler] of Object.entries(commands)) context.subscriptions.push(vscode.commands.registerCommand(`prope.${name}`, () => handler().catch((error: unknown) => vscode.window.showErrorMessage(t('Prope operation failed: {0}', error instanceof ConnectorError ? error.code : 'invalid_request')))));
  context.subscriptions.push(output, { dispose: () => { panel.dispose(); broker.close(); void unlink(endpoint.fsPath).catch(() => undefined); } });
}
