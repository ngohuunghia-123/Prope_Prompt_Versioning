import { lazy, Suspense, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';

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
  const titleKey = pathname === '/app/reviews' ? 'review.queue.pageTitle' : pathname.endsWith('/similar-check') ? 'similar.pageTitle' : pathname.endsWith('/restore') ? 'restore.pageTitle' : pathname.endsWith('/release') ? 'release.pageTitle' : pathname.endsWith('/review') ? 'review.pageTitle' : pathname.endsWith('/evaluation') ? 'evaluation.pageTitle' : pathname.includes('/revisions/compare/') ? 'revisions.compare.pageTitle' : pathname.endsWith('/revisions/new') ? 'revisions.editor.pageTitle' : pathname.endsWith('/revisions') ? 'revisions.pageTitle' : pathname.endsWith('/access') ? 'accessManagement.pageTitle' : pathname.startsWith('/app/registry/') ? 'trustedRegistry.detail.pageTitle' : pathname === '/app/registry' ? 'trustedRegistry.title' : pathname.endsWith('/new') ? 'registration.pageTitle' : 'preservation.detail.pageTitle';
  useEffect(() => { document.title = `${t('meta.product')} — ${t(titleKey)}`; }, [t, titleKey]);
  return (
    <Suspense fallback={<div className="grid min-h-dvh place-items-center bg-canvas text-body text-muted">{t('common.loading')}</div>}>
      <Routes>
        <Route path="/" element={<Navigate to="/app/registry" replace />} />
        <Route path="/app" element={<Navigate to="/app/registry" replace />} />
        <Route path="/app/welcome" element={<Navigate to="/app/registry" replace />} />
        <Route path="/app/prompts" element={<Navigate to="/app/registry" replace />} />
        <Route path="/app/reviews" element={<ReviewQueuePage />} />
        <Route path="/app/prompts/similar-check" element={<SimilarPromptCheckPage />} />
        <Route path="/app/prompts/new" element={<AddPromptPage />} />
        <Route path="/app/prompts/:id/access" element={<AccessManagementPage />} />
        <Route path="/app/prompts/:id/revisions" element={<RevisionHistoryPage />} />
        <Route path="/app/prompts/:id/revisions/new" element={<RevisionEditorPage />} />
        <Route path="/app/prompts/:id/revisions/compare/:revisionId" element={<RevisionComparePage />} />
        <Route path="/app/prompts/:id/evaluation" element={<EvaluationEvidencePage />} />
        <Route path="/app/prompts/:id/review" element={<ReviewApprovalPage />} />
        <Route path="/app/prompts/:id/release" element={<ReleaseApprovedRevisionPage />} />
        <Route path="/app/prompts/:id/restore" element={<RestoreRevisionPage />} />
        <Route path="/app/prompts/:id" element={<PromptDetailPage />} />
        <Route path="/app/registry" element={<TrustedRegistryPage />} />
        <Route path="/app/registry/:id" element={<TrustedPromptDetailPage />} />
        <Route path="*" element={<Navigate to="/app/registry" replace />} />
      </Routes>
    </Suspense>
  );
}
