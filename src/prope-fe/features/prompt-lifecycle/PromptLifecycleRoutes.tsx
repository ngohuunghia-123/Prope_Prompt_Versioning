import { lazy, Suspense } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, Route, Routes } from 'react-router-dom';

const PromptRegistryPage = lazy(() => import('@/features/prompt-lifecycle/PromptRegistryPage').then((module) => ({ default: module.PromptRegistryPage })));
const PromptDetailPage = lazy(() => import('@/features/prompt-lifecycle/PromptDetailPage').then((module) => ({ default: module.PromptDetailPage })));
const PromptEditorPage = lazy(() => import('@/features/prompt-lifecycle/PromptEditorPage').then((module) => ({ default: module.PromptEditorPage })));
const ReviewQueuePage = lazy(() => import('@/features/prompt-lifecycle/ReviewQueuePage').then((module) => ({ default: module.ReviewQueuePage })));
const ReviewDetailPage = lazy(() => import('@/features/prompt-lifecycle/ReviewDetailPage').then((module) => ({ default: module.ReviewDetailPage })));
const ReleasePage = lazy(() => import('@/features/prompt-lifecycle/ReleasePage').then((module) => ({ default: module.ReleasePage })));
const ProvidersPage = lazy(() => import('@/features/prompt-lifecycle/ProvidersPage').then((module) => ({ default: module.ProvidersPage })));
// There is no `CallRecordsPage` any more. ADR-0055 makes the call-record read
// per prompt and behind `prompt.read`, because every record names a prompt id and
// a workspace-wide list would say that a private prompt exists (BR-01). The view
// lives on the prompt detail screen as `PromptProductionLogs`; `/app/calls`
// redirects there rather than 404ing on a link somebody has bookmarked.

export function PromptLifecycleRoutes() {
  const { t } = useTranslation();
  return (
    <Suspense fallback={<div role="status" className="grid min-h-64 place-items-center rounded-modal border border-border bg-surface text-body text-muted shadow-panel">{t('common.loading')}</div>}>
      <Routes>
        <Route path="prompts" element={<PromptRegistryPage />} />
        <Route path="prompts/new" element={<PromptEditorPage />} />
        <Route path="prompts/:promptId" element={<PromptDetailPage />} />
        <Route path="prompts/:promptId/revisions/new" element={<PromptEditorPage />} />
        <Route path="reviews" element={<ReviewQueuePage />} />
        <Route path="reviews/:promptId/:versionId" element={<ReviewDetailPage />} />
        <Route path="releases/:promptId/:versionId" element={<ReleasePage />} />
        <Route path="providers" element={<ProvidersPage />} />
        <Route path="calls" element={<Navigate to="/app/prompts" replace />} />
        <Route path="vault/folder-1" element={<Navigate to="/app/prompts" replace />} />
        <Route path="vault/folder-1/customer-support" element={<Navigate to="/app/prompts" replace />} />
        <Route path="vault/folder-1/claim-screening" element={<Navigate to="/app/prompts" replace />} />
        <Route path="evaluation/review-queue" element={<Navigate to="/app/reviews" replace />} />
        <Route path="evaluation/datasets" element={<Navigate to="/app/prompts" replace />} />
        <Route path="evaluation/reports" element={<Navigate to="/app/prompts" replace />} />
        <Route path="*" element={<Navigate to="/app/prompts" replace />} />
      </Routes>
    </Suspense>
  );
}
