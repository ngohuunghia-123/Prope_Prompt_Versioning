import { lazy, Suspense } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, Route, Routes } from 'react-router-dom';

const PromptDetailPage = lazy(() => import('@/features/prompt-lifecycle/PromptDetailPage').then((module) => ({ default: module.PromptDetailPage })));
const PromptFoldersPage = lazy(() => import('@/features/prompt-lifecycle/PromptFoldersPage').then((module) => ({ default: module.PromptFoldersPage })));
const PromptSearchPage = lazy(() => import('@/features/prompt-lifecycle/PromptSearchPage').then((module) => ({ default: module.PromptSearchPage })));
const FolderDetailPage = lazy(() => import('@/features/prompt-lifecycle/FolderDetailPage').then((module) => ({ default: module.FolderDetailPage })));
const PromptEditorPage = lazy(() => import('@/features/prompt-lifecycle/PromptEditorPage').then((module) => ({ default: module.PromptEditorPage })));
const PromptWizardPage = lazy(() => import('@/features/prompt-lifecycle/PromptWizardPage').then((module) => ({ default: module.PromptWizardPage })));
const PromptTestPage = lazy(() => import('@/features/prompt-lifecycle/PromptTestPage').then((module) => ({ default: module.PromptTestPage })));
const ReviewQueuePage = lazy(() => import('@/features/prompt-lifecycle/ReviewQueuePage').then((module) => ({ default: module.ReviewQueuePage })));
const ReviewDetailPage = lazy(() => import('@/features/prompt-lifecycle/ReviewDetailPage').then((module) => ({ default: module.ReviewDetailPage })));
const ReleasePage = lazy(() => import('@/features/prompt-lifecycle/ReleasePage').then((module) => ({ default: module.ReleasePage })));
const ProvidersPage = lazy(() => import('@/features/prompt-lifecycle/ProvidersPage').then((module) => ({ default: module.ProvidersPage })));
const CallRecordsPage = lazy(() => import('@/features/prompt-lifecycle/CallRecordsPage').then((module) => ({ default: module.CallRecordsPage })));
const PlaygroundPage = lazy(() => import('@/features/prompt-lifecycle/PlaygroundPage').then((module) => ({ default: module.PlaygroundPage })));
const EvalRunPage = lazy(() => import('@/features/prompt-lifecycle/EvalRunPage').then((module) => ({ default: module.EvalRunPage })));
const ProductionPage = lazy(() => import('@/features/prompt-lifecycle/ProductionPage').then((module) => ({ default: module.ProductionPage })));
const DatasetPage = lazy(() => import('@/features/prompt-lifecycle/DatasetPage').then((module) => ({ default: module.DatasetPage })));
const DatasetDetailPage = lazy(() => import('@/features/prompt-lifecycle/DatasetDetailPage').then((module) => ({ default: module.DatasetDetailPage })));

export function PromptLifecycleRoutes() {
  const { t } = useTranslation();
  return (
    <Suspense fallback={<div role="status" className="grid min-h-64 place-items-center rounded-modal border border-border bg-surface text-body text-muted shadow-panel">{t('common.loading')}</div>}>
      <Routes>
        {/* Folder slugs come from the registry's namespaces, so they sit behind a
            static `folder/` segment to stay unambiguous against /prompts/:promptId. */}
        <Route path="prompts" element={<PromptFoldersPage />}>
          <Route index element={<FolderDetailPage />} />
          <Route path="folder/:folderId" element={<FolderDetailPage />} />
        </Route>

        {/* Individual prompt detail routes (sibling, not nested under /prompts to avoid route conflicts) */}
        <Route path="prompts/:promptId" element={<PromptDetailPage />} />
        <Route path="prompts/:promptId/edit" element={<PromptEditorPage />} />
        <Route path="prompts/:promptId/test" element={<PromptTestPage />} />
        <Route path="prompts/:promptId/playground" element={<PlaygroundPage />} />
        <Route path="prompts/:promptId/evaluation" element={<PromptDetailPage />} />
        <Route path="prompts/:promptId/logs" element={<PromptDetailPage />} />
        <Route path="prompts/:promptId/production" element={<PromptDetailPage />} />
        <Route path="prompts/:promptId/evaluation/run" element={<EvalRunPage />} />
        <Route path="prompts/:promptId/logs/all" element={<CallRecordsPage />} />
        <Route path="prompts/:promptId/production/dashboard" element={<ProductionPage />} />
        <Route path="prompts/:promptId/revisions/new" element={<Navigate to="../edit" replace />} />

        {/* Prompt creation routes */}
        <Route path="prompts/new" element={<PromptEditorPage />} />
        <Route path="prompts/new/wizard" element={<PromptWizardPage />} />

        {/* Other routes */}
        <Route path="search" element={<PromptSearchPage />} />
        <Route path="reviews" element={<ReviewQueuePage />} />
        <Route path="reviews/:reviewId" element={<ReviewDetailPage />} />
        <Route path="releases/:revisionId" element={<ReleasePage />} />
        <Route path="providers" element={<ProvidersPage />} />
        <Route path="calls" element={<CallRecordsPage />} />
        <Route path="datasets" element={<DatasetPage />} />
        <Route path="datasets/:datasetId" element={<DatasetDetailPage />} />

        {/* Legacy redirects */}
        <Route path="vault/folder-1" element={<Navigate to="/app/prompts" replace />} />
        <Route path="vault/folder-1/customer-support" element={<Navigate to="/app/prompts/checkout-assistant" replace />} />
        <Route path="vault/folder-1/claim-screening" element={<Navigate to="/app/prompts/support-triage" replace />} />
        <Route path="evaluation/review-queue" element={<Navigate to="/app/reviews" replace />} />
        <Route path="evaluation/datasets" element={<Navigate to="/app/datasets" replace />} />
        <Route path="evaluation/reports" element={<Navigate to="/app/prompts/checkout-assistant/production" replace />} />

        {/* Default fallback */}
        <Route path="*" element={<Navigate to="/app/prompts" replace />} />
      </Routes>
    </Suspense>
  );
}
