import { lazy, Suspense, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { ComponentLabPage } from '@/features/component-lab/ComponentLabPage';

const LandingPage = lazy(() => import('@/features/landing/LandingPage').then((module) => ({ default: module.LandingPage })));
const LegalPage = lazy(() => import('@/features/landing/LegalPage').then((module) => ({ default: module.LegalPage })));
const LoginPage = lazy(() => import('@/features/auth/LoginPage').then((module) => ({ default: module.LoginPage })));

export function App() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const titleKey = pathname === '/' ? 'meta.home' : pathname === '/login' ? 'meta.login' : pathname === '/privacy' ? 'meta.privacy' : pathname === '/terms' ? 'meta.terms' : pathname === '/components' ? 'componentLab.title' : 'meta.home';
  useEffect(() => { document.title = `${t('meta.product')} — ${t(titleKey)}`; }, [t, titleKey]);
  return (
    <Suspense fallback={<div className="grid min-h-dvh place-items-center bg-canvas text-body text-muted">{t('common.loading')}</div>}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/privacy" element={<LegalPage />} />
        <Route path="/terms" element={<LegalPage />} />
        <Route path="/components" element={<ComponentLabPage />} />
        <Route path="/app" element={<Navigate to="/components" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
