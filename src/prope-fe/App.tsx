import { lazy, Suspense, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { AuthRoute } from '@/features/auth/components/AuthRoute';
import { AuthSessionListener } from '@/features/auth/components/AuthSessionListener';
import { ChatProvider } from '@/features/chat/ChatProvider';
import { ComponentLabPage } from '@/features/component-lab/ComponentLabPage';
import { StaticLandingRedirect } from '@/features/landing/StaticLandingRedirect';
import { RouteLoadingState, type RouteLoadingKind } from '@/components/ui/RouteLoadingState';

const LoginPage = lazy(() => import('@/features/auth/LoginPage').then((module) => ({ default: module.LoginPage })));
const ChangePasswordPage = lazy(() => import('@/features/auth/ChangePasswordPage').then((module) => ({ default: module.ChangePasswordPage })));
const WorkspacePage = lazy(() => import('@/features/workspace/WorkspacePage').then((module) => ({ default: module.WorkspacePage })));
const WorkspaceChooserPage = lazy(() => import('@/features/auth/WorkspaceChooserPage').then((module) => ({ default: module.WorkspaceChooserPage })));

export function App() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const loadingKind: RouteLoadingKind = pathname === '/' ? 'redirect' : pathname === '/login' || pathname === '/signup' ? 'auth' : pathname === '/change-password' ? 'form' : pathname === '/workspaces' ? 'workspace' : 'app';
  const titleKey = pathname === '/dev/component' ? 'componentLab.title' : pathname === '/change-password' ? 'meta.changePassword' : pathname === '/signup' ? 'meta.signup' : pathname === '/workspaces' ? 'meta.chooser' : pathname.startsWith('/app') ? 'meta.home' : 'meta.login';
  useEffect(() => { document.title = `${t('meta.product')} — ${t(titleKey)}`; }, [t, titleKey]);

  return (
    <>
      <AuthSessionListener />
      <Suspense fallback={<RouteLoadingState label={t('common.loading')} kind={loadingKind} />}>
        <Routes>
          <Route path="/" element={<StaticLandingRedirect />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<LoginPage />} />
          <Route path="/change-password" element={<ChangePasswordPage />} />
          <Route path="/dev/component" element={<ComponentLabPage />} />
          {/* The lobby (ADR-0056). Outside `AuthRoute`, because that guard sends
              a workspace-less session HERE — putting the chooser behind it would
              be a redirect to itself. It does its own signed-in check and its own
              redirect to the sign-in screen. */}
          <Route path="/workspaces" element={<WorkspaceChooserPage />} />
          <Route path="/app" element={<Navigate to="/app/prompts" replace />} />
          {/* The provider sits inside AuthRoute, because an unauthenticated
              visitor must not open a conversation, and inside the Router,
              because a `navigate` directive needs one. */}
          <Route path="/app/*" element={<AuthRoute><ChatProvider><WorkspacePage /></ChatProvider></AuthRoute>} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </Suspense>
    </>
  );
}
