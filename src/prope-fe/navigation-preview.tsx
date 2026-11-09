import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import '@/locales/i18n';
import '@/theme.css';
import { WorkspacePage } from '@/features/workspace/WorkspacePage';

const root = document.getElementById('root');
if (!root) throw new Error('Preview root is missing.');
const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } });

createRoot(root).render(<StrictMode><QueryClientProvider client={queryClient}><BrowserRouter><WorkspacePage /></BrowserRouter></QueryClientProvider></StrictMode>);
