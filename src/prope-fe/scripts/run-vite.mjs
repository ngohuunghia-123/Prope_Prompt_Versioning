import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';

const nodeBinary = resolve('node_modules', 'node', 'bin', process.platform === 'win32' ? 'node.exe' : 'node');
const viteCli = resolve('node_modules', 'vite', 'bin', 'vite.js');
const result = spawnSync(nodeBinary, [viteCli, ...process.argv.slice(2)], { stdio: 'inherit' });

process.exit(result.status ?? 1);
