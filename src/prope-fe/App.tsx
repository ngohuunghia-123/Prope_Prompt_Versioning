import { lazy, Suspense, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { AuthRoute } from '@/features/auth/components/AuthRoute';
import { AuthSessionListener } from '@/features/auth/components/AuthSessionListener';
import { StaticLandingRedirect } from '@/features/landing/StaticLandingRedirect';
import { ComponentLabPage } from '@/features/component-lab/ComponentLabPage';

const LoginPage = lazy(() => import('@/features/auth/LoginPage').then((module) => ({ default: module.LoginPage })));
const ChangePasswordPage = lazy(() => import('@/features/auth/ChangePasswordPage').then((module) => ({ default: module.ChangePasswordPage })));
const WorkspacePage = lazy(() => import('@/features/workspace/WorkspacePage').then((module) => ({ default: module.WorkspacePage })));

export function App() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const titleKey = pathname === '/dev/component' ? 'componentLab.title' : pathname === '/change-password' ? 'meta.changePassword' : pathname === '/signup' ? 'meta.signup' : pathname.startsWith('/app') ? 'meta.home' : 'meta.login';
  useEffect(() => { document.title = `${t('meta.product')} — ${t(titleKey)}`; }, [t, titleKey]);
  return (
    <>
      <AuthSessionListener />
      <Suspense fallback={<div className="grid min-h-dvh place-items-center bg-canvas text-body text-muted">{t('common.loading')}</div>}>
        <Routes>
          <Route path="/" element={<StaticLandingRedirect />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<LoginPage />} />
          <Route path="/change-password" element={<ChangePasswordPage />} />
          <Route path="/dev/component" element={<ComponentLabPage />} />
          <Route path="/app" element={<Navigate to="/app/prompts" replace />} />
          <Route path="/app/*" element={<AuthRoute><WorkspacePage /></AuthRoute>} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </Suspense>
    </>
  );
}
