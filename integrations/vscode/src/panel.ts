import * as vscode from 'vscode';
import { randomBytes } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { z } from 'zod';
import { webviewRequestSchema } from '@connector/contracts';
import { ConnectorError } from './api';

export class Panel {
  private panel: vscode.WebviewPanel | undefined;
  constructor(private readonly context: vscode.ExtensionContext,
    private readonly dispatch: (action: string, payload: unknown) => Promise<unknown>,
    private readonly closed: () => void) {}
  async open() {
    if (this.panel) { this.panel.reveal(vscode.ViewColumn.Beside); return; }
    const root = vscode.Uri.joinPath(this.context.extensionUri, 'dist/media');
    const panel = vscode.window.createWebviewPanel('prope', 'Prope', vscode.ViewColumn.Beside, { enableScripts: true, localResourceRoots: [root], retainContextWhenHidden: false });
    this.panel = panel;
    const nonce = randomBytes(24).toString('base64');
    const manifest = z.record(z.string(), z.object({ file: z.string(), css: z.array(z.string()).optional() })).parse(JSON.parse(await readFile(vscode.Uri.joinPath(root, '.vite/manifest.json').fsPath, 'utf8')));
    const entry = manifest['features/connectors/entry.tsx'];
    if (!entry) throw new ConnectorError('webview_bundle_missing');
    const styles = [...new Set([...(entry.css ?? []), ...(manifest['style.css'] ? [manifest['style.css'].file] : [])])];
    const uri = (file: string) => panel.webview.asWebviewUri(vscode.Uri.joinPath(root, file));
    panel.webview.html = `<!doctype html><html><head><meta charset="UTF-8"><meta name="prope-assets" content="${uri('')}"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'nonce-${nonce}'; style-src ${panel.webview.cspSource}; font-src ${panel.webview.cspSource}; img-src ${panel.webview.cspSource} data:; connect-src 'none';">${styles.map((file) => `<link rel="stylesheet" href="${uri(file)}">`).join('')}</head><body><div id="root"></div><script nonce="${nonce}" type="module" src="${uri(entry.file)}"></script></body></html>`;
    panel.onDidDispose(() => { this.panel = undefined; this.closed(); });
    panel.webview.onDidReceiveMessage((raw: unknown) => {
      const parsed = webviewRequestSchema.safeParse(raw); if (!parsed.success) return;
      const { id, action, payload } = parsed.data;
      void this.dispatch(action, payload).then((data) => panel.webview.postMessage({ type: 'response', id, ok: true, data }))
        .catch((error: unknown) => panel.webview.postMessage({ type: 'response', id, ok: false,
          error: { code: error instanceof ConnectorError ? error.code : 'invalid_request', request_id: error instanceof ConnectorError ? error.requestId : undefined } }));
    });
  }
  changed(reset = false) { void this.panel?.webview.postMessage({ type: 'changed', reset }); }
  dispose() { this.panel?.dispose(); }
}
