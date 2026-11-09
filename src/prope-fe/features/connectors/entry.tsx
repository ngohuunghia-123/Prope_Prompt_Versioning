import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import '@/locales/i18n';
import '@/connector-theme.css';
import { onHostChanged } from '@/features/connectors/bridge';
import { ConnectorPanel } from '@/features/connectors/ConnectorPanel';

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false }, mutations: { retry: false } } });
const applyTheme = () => { document.documentElement.dataset.theme = document.body.classList.contains('vscode-dark') || document.body.classList.contains('vscode-high-contrast') ? 'dark' : 'light'; };
applyTheme();
new MutationObserver(applyTheme).observe(document.body, { attributes: true, attributeFilter: ['class'] });
onHostChanged((reset) => {
  if (reset) { queryClient.getMutationCache().clear(); void queryClient.resetQueries(); }
  else void queryClient.invalidateQueries();
});
const root = document.getElementById('root');
if (!root) throw new Error('Root element not found');
createRoot(root).render(<StrictMode><QueryClientProvider client={queryClient}><ConnectorPanel /></QueryClientProvider></StrictMode>);
