import { build } from 'esbuild';
import { spawnSync } from 'node:child_process';
import { readdir, readFile, writeFile, mkdir, copyFile } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const frontend = resolve(root, '../../src/prope-fe');
const result = spawnSync(process.execPath, [resolve(frontend, 'node_modules/vite/bin/vite.js'), 'build', '--config', 'vite.connector.config.ts'], { cwd: frontend, stdio: 'inherit' });
if (result.status !== 0) process.exit(result.status ?? 1);
await mkdir(resolve(root, 'dist/media/assets/mascot'), { recursive: true });
for (const name of ['avatar.webp', 'empty-state.webp', 'idle.webp', 'mascot-animate.gif']) {
  await copyFile(resolve(frontend, 'public/assets/mascot', name), resolve(root, 'dist/media/assets/mascot', name));
}
// The shared theme has a Google Fonts import; an offline Webview uses its local fallbacks.
for (const name of await readdir(resolve(root, 'dist/media'))) if (name.endsWith('.css')) {
  const path = resolve(root, 'dist/media', name);
  const css = await readFile(path, 'utf8');
  await writeFile(path, css.replace(/@import\s*(?:url\(\s*)?(['"])https:\/\/fonts\.googleapis\.com\/[^'"]*\1\s*\)?\s*;/g, ''));
}
await build({ absWorkingDir: root, entryPoints: ['src/extension.ts'], outfile: 'dist/extension.cjs', bundle: true, platform: 'node', format: 'cjs', target: 'node22', external: ['vscode'], tsconfig: 'tsconfig.json' });
await build({ absWorkingDir: root, entryPoints: ['src/mcp-stdio.ts'], outfile: 'dist/mcp-stdio.mjs', bundle: true, platform: 'node', format: 'esm', target: 'node22', tsconfig: 'tsconfig.json', banner: { js: "import { createRequire as __createRequire } from 'node:module'; const require = __createRequire(import.meta.url);" } });
await mkdir(resolve(root, 'dist'), { recursive: true });
