import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';

const bundledNode = resolve('node_modules', 'node', 'bin', process.platform === 'win32' ? 'node.exe' : 'node');
const nodeBinary = existsSync(bundledNode) ? bundledNode : process.execPath;
const viteCli = resolve('node_modules', 'vite', 'bin', 'vite.js');
const result = spawnSync(nodeBinary, [viteCli, ...process.argv.slice(2)], { stdio: 'inherit' });

process.exit(result.status ?? 1);
