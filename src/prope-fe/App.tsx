import { lazy, Suspense, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { AuthRoute } from '@/features/auth/components/AuthRoute';
import { AuthSessionListener } from '@/features/auth/components/AuthSessionListener';
import { ComponentLabPage } from '@/features/component-lab/ComponentLabPage';
import { StaticLandingRedirect } from '@/features/landing/StaticLandingRedirect';

const LoginPage = lazy(() => import('@/features/auth/LoginPage').then((module) => ({ default: module.LoginPage })));
const ChangePasswordPage = lazy(() => import('@/features/auth/ChangePasswordPage').then((module) => ({ default: module.ChangePasswordPage })));
const AddPromptPage = lazy(() => import('@/features/preservation/AddPromptPage').then((module) => ({ default: module.AddPromptPage })));
const PromptDetailPage = lazy(() => import('@/features/preservation/PromptDetailPage').then((module) => ({ default: module.PromptDetailPage })));
const TrustedRegistryPage = lazy(() => import('@/features/trusted-registry/TrustedRegistryPage').then((module) => ({ default: module.TrustedRegistryPage })));
const TrustedPromptDetailPage = lazy(() => import('@/features/trusted-registry/TrustedPromptDetailPage').then((module) => ({ default: module.TrustedPromptDetailPage })));
const AccessManagementPage = lazy(() => import('@/features/access-management/AccessManagementPage').then((module) => ({ default: module.AccessManagementPage })));
const RevisionHistoryPage = lazy(() => import('@/features/revisions/RevisionHistoryPage').then((module) => ({ default: module.RevisionHistoryPage })));
const RevisionEditorPage = lazy(() => import('@/features/revisions/RevisionEditorPage').then((module) => ({ default: module.RevisionEditorPage })));
const RevisionComparePage = lazy(() => import('@/features/revisions/RevisionComparePage').then((module) => ({ default: module.RevisionComparePage })));
const EvaluationEvidencePage = lazy(() => import('@/features/evaluation/EvaluationEvidencePage').then((module) => ({ default: module.EvaluationEvidencePage })));
const ReviewApprovalPage = lazy(() => import('@/features/review/ReviewApprovalPage').then((module) => ({ default: module.ReviewApprovalPage })));
const ReviewQueuePage = lazy(() => import('@/features/review/ReviewQueuePage').then((module) => ({ default: module.ReviewQueuePage })));
const ReleaseApprovedRevisionPage = lazy(() => import('@/features/release-control/ReleaseApprovedRevisionPage').then((module) => ({ default: module.ReleaseApprovedRevisionPage })));
const RestoreRevisionPage = lazy(() => import('@/features/release-control/RestoreRevisionPage').then((module) => ({ default: module.RestoreRevisionPage })));
const SimilarPromptCheckPage = lazy(() => import('@/features/similar-check/SimilarPromptCheckPage').then((module) => ({ default: module.SimilarPromptCheckPage })));

export function App() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const titleKey = pathname === '/dev/component' ? 'componentLab.title' : pathname === '/change-password' ? 'meta.changePassword' : pathname === '/signup' ? 'meta.signup' : pathname === '/app/reviews' ? 'review.queue.pageTitle' : pathname.endsWith('/similar-check') ? 'similar.pageTitle' : pathname.endsWith('/restore') ? 'restore.pageTitle' : pathname.endsWith('/release') ? 'release.pageTitle' : pathname.endsWith('/review') ? 'review.pageTitle' : pathname.endsWith('/evaluation') ? 'evaluation.pageTitle' : pathname.includes('/revisions/compare/') ? 'revisions.compare.pageTitle' : pathname.endsWith('/revisions/new') ? 'revisions.editor.pageTitle' : pathname.endsWith('/revisions') ? 'revisions.pageTitle' : pathname.endsWith('/access') ? 'accessManagement.pageTitle' : pathname.startsWith('/app/registry/') ? 'trustedRegistry.detail.pageTitle' : pathname === '/app/registry' ? 'trustedRegistry.title' : pathname.endsWith('/new') ? 'registration.pageTitle' : pathname.startsWith('/app') ? 'preservation.detail.pageTitle' : 'meta.login';
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
          <Route path="/app" element={<Navigate to="/app/registry" replace />} />
          <Route path="/app/welcome" element={<Navigate to="/app/registry" replace />} />
          <Route path="/app/prompts" element={<Navigate to="/app/registry" replace />} />
          <Route path="/app/reviews" element={<AuthRoute><ReviewQueuePage /></AuthRoute>} />
          <Route path="/app/prompts/similar-check" element={<AuthRoute><SimilarPromptCheckPage /></AuthRoute>} />
          <Route path="/app/prompts/new" element={<AuthRoute><AddPromptPage /></AuthRoute>} />
          <Route path="/app/prompts/:id/access" element={<AuthRoute><AccessManagementPage /></AuthRoute>} />
          <Route path="/app/prompts/:id/revisions" element={<AuthRoute><RevisionHistoryPage /></AuthRoute>} />
          <Route path="/app/prompts/:id/revisions/new" element={<AuthRoute><RevisionEditorPage /></AuthRoute>} />
          <Route path="/app/prompts/:id/revisions/compare/:revisionId" element={<AuthRoute><RevisionComparePage /></AuthRoute>} />
          <Route path="/app/prompts/:id/evaluation" element={<AuthRoute><EvaluationEvidencePage /></AuthRoute>} />
          <Route path="/app/prompts/:id/review" element={<AuthRoute><ReviewApprovalPage /></AuthRoute>} />
          <Route path="/app/prompts/:id/release" element={<AuthRoute><ReleaseApprovedRevisionPage /></AuthRoute>} />
          <Route path="/app/prompts/:id/restore" element={<AuthRoute><RestoreRevisionPage /></AuthRoute>} />
          <Route path="/app/prompts/:id" element={<AuthRoute><PromptDetailPage /></AuthRoute>} />
          <Route path="/app/registry" element={<AuthRoute><TrustedRegistryPage /></AuthRoute>} />
          <Route path="/app/registry/:id" element={<AuthRoute><TrustedPromptDetailPage /></AuthRoute>} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </Suspense>
    </>
  );
}
