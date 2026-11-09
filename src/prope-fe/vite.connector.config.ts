import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  publicDir: false,
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': fileURLToPath(new URL('.', import.meta.url)) } },
  define: { 'process.env.NODE_ENV': JSON.stringify('production'), 'import.meta.env.VITE_DATA_MODE': JSON.stringify('api'), 'import.meta.env.VITE_AUTH_MODE': JSON.stringify('api') },
  build: {
    outDir: '../../integrations/vscode/dist/media', emptyOutDir: true, manifest: true,
    lib: { entry: 'features/connectors/entry.tsx', formats: ['es'], fileName: 'connector' },
    rollupOptions: { output: { inlineDynamicImports: true } },
    cssCodeSplit: false, minify: 'esbuild',
  },
});
