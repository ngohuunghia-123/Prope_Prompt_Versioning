import { fileURLToPath, URL } from 'node:url';
import DevInspector from '@mcpc-tech/unplugin-dev-inspector-mcp';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// The dev server reproduces the Caddyfile's single-origin split (see Caddyfile
// header): the SPA and the API share one origin so ADR-0029's HttpOnly/SameSite
// cookie works with no CORS and no CSRF token. In Docker the API is the `app`
// service; outside Docker it is localhost. `VITE_API_PROXY_TARGET` selects.
const apiProxyTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000';
const apiProxyPaths = ['/api', '/v1', '/metrics', '/healthz', '/readyz'];
// Bind-mounted source on a Windows host does not deliver inotify events into a
// Linux container, so file watching has to poll there. Opt-in via env so native
// (macOS/Linux) dev keeps event-based watching.
const usePolling = process.env.VITE_USE_POLLING === 'true';

export default defineConfig({
  plugins: [DevInspector.vite({ enabled: process.env.VITE_DEV_INSPECTOR !== 'false' }), react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    proxy: Object.fromEntries(
      apiProxyPaths.map((path) => [path, { target: apiProxyTarget, changeOrigin: true }]),
    ),
    watch: usePolling ? { usePolling: true } : undefined,
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'query-vendor': ['@tanstack/react-query'],
          'i18n-vendor': ['i18next', 'react-i18next'],
          'icons-vendor': ['@phosphor-icons/react'],
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('.', import.meta.url)),
    },
  },
});
