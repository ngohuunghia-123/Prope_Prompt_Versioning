import { fileURLToPath, URL } from 'node:url';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

/**
 * Where the dev server forwards API traffic. Override with `PROPE_API_ORIGIN`
 * when the application is not on the default port — running it under
 * `docker compose` puts Caddy on `:8080` rather than uvicorn on `:8000`.
 */
const apiOrigin = process.env.PROPE_API_ORIGIN ?? 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  /**
   * **The dev server must be the same origin as the API, not merely able to
   * reach it.** Prope's session cookie is `SameSite=Lax` with no CORS
   * configuration and no CSRF token anywhere in the product, and ADR-0052 is
   * explicit that this is safe *because* the SPA is same-origin. A dev setup that
   * pointed `fetch` at `http://localhost:8000` directly would need CORS and
   * `credentials: 'include'` across origins — which is a second security posture,
   * exercised only in development, diverging from the one that ships.
   *
   * So the paths in `apiClient` are origin-relative in both environments and this
   * proxy is what makes that true locally: `/api` for the management surface,
   * `/v1` for the OpenAI-compatible gateway. It mirrors the `handle_path` blocks
   * in the `Caddyfile`, and the two are meant to be read together.
   */
  server: {
    proxy: {
      '/api': { target: apiOrigin, changeOrigin: false },
      '/v1': { target: apiOrigin, changeOrigin: false },
      // Not strictly needed by the SPA, but it makes `curl localhost:5173/readyz`
      // answer the same thing the deployed origin does while debugging.
      '/healthz': { target: apiOrigin, changeOrigin: false },
      '/readyz': { target: apiOrigin, changeOrigin: false },
    },
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
