import { lazy, Suspense } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, Route, Routes, useLocation, useParams } from 'react-router-dom';
import { DelayedContentSkeleton } from '@/components/ui/DelayedContentSkeleton';
import type { ContentSkeletonLayout } from '@/components/ui/ContentSkeleton';

const PromptDetailPage = lazy(() => import('@/features/prompt-lifecycle/PromptDetailPage').then((module) => ({ default: module.PromptDetailPage })));
const PromptFoldersPage = lazy(() => import('@/features/prompt-lifecycle/PromptFoldersPage').then((module) => ({ default: module.PromptFoldersPage })));
const PromptSearchPage = lazy(() => import('@/features/prompt-lifecycle/PromptSearchPage').then((module) => ({ default: module.PromptSearchPage })));
const FolderDetailPage = lazy(() => import('@/features/prompt-lifecycle/FolderDetailPage').then((module) => ({ default: module.FolderDetailPage })));
const PromptEditorPage = lazy(() => import('@/features/prompt-lifecycle/PromptEditorPage').then((module) => ({ default: module.PromptEditorPage })));
const PromptTestPage = lazy(() => import('@/features/prompt-lifecycle/PromptTestPage').then((module) => ({ default: module.PromptTestPage })));
const ReviewQueuePage = lazy(() => import('@/features/prompt-lifecycle/ReviewQueuePage').then((module) => ({ default: module.ReviewQueuePage })));
const ReviewDetailPage = lazy(() => import('@/features/prompt-lifecycle/ReviewDetailPage').then((module) => ({ default: module.ReviewDetailPage })));
const ProvidersPage = lazy(() => import('@/features/prompt-lifecycle/ProvidersPage').then((module) => ({ default: module.ProvidersPage })));
const PlaygroundPage = lazy(() => import('@/features/prompt-lifecycle/PlaygroundPage').then((module) => ({ default: module.PlaygroundPage })));
const EvalRunPage = lazy(() => import('@/features/prompt-lifecycle/EvalRunPage').then((module) => ({ default: module.EvalRunPage })));
const DatasetPage = lazy(() => import('@/features/prompt-lifecycle/DatasetPage').then((module) => ({ default: module.DatasetPage })));
const DatasetDetailPage = lazy(() => import('@/features/prompt-lifecycle/DatasetDetailPage').then((module) => ({ default: module.DatasetDetailPage })));
const LabelingPage = lazy(() => import('@/features/labeling/LabelingPage').then((module) => ({ default: module.LabelingPage })));
const ApiKeysPage = lazy(() => import('@/features/workspace/ApiKeysPage').then((module) => ({ default: module.ApiKeysPage })));
const WorkspaceMembersPage = lazy(() => import('@/features/workspace/WorkspaceMembersPage').then((module) => ({ default: module.WorkspaceMembersPage })));
const AccountPage = lazy(() => import('@/features/account/AccountPage').then((module) => ({ default: module.AccountPage })));
const ProfilePage = lazy(() => import('@/features/account/ProfilePage').then((module) => ({ default: module.ProfilePage })));
const ImportUploadPage = lazy(() => import('@/features/prompt-ingestion/ImportUploadPage').then((module) => ({ default: module.ImportUploadPage })));
const ImportReviewPage = lazy(() => import('@/features/prompt-ingestion/ImportReviewPage').then((module) => ({ default: module.ImportReviewPage })));

function ReleaseRedirect() {
  const { revisionId } = useParams();
  return <Navigate to={revisionId ? `/app/prompts/${revisionId}?tab=release` : '/app/prompts'} replace />;
}

function LegacyPromptTabRedirect({ tab }: { tab: 'release' | 'production' | 'evaluation' }) {
  const { promptId } = useParams();
  return <Navigate to={promptId ? `/app/prompts/${promptId}?tab=${tab}` : '/app/prompts'} replace />;
}

export function PromptLifecycleRoutes() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  let loadingLayout: ContentSkeletonLayout = 'page';
  if (/\/(edit|test|playground)$/.test(pathname) || pathname === '/app/playground') loadingLayout = 'form';
  else if (/\/(reviews|providers|keys|workspace)$/.test(pathname)) loadingLayout = 'table';
  else if (/\/(prompts|search|datasets)$/.test(pathname)) loadingLayout = 'cards';
  return (
    <Suspense fallback={<DelayedContentSkeleton label={t('common.loading')} layout={loadingLayout} />}>
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
        <Route path="prompts/:promptId/release" element={<LegacyPromptTabRedirect tab="release" />} />
        <Route path="prompts/:promptId/evaluation" element={<LegacyPromptTabRedirect tab="evaluation" />} />
        <Route path="prompts/:promptId/logs" element={<LegacyPromptTabRedirect tab="production" />} />
        <Route path="prompts/:promptId/production" element={<LegacyPromptTabRedirect tab="production" />} />
        <Route path="prompts/:promptId/evaluation/run" element={<EvalRunPage />} />
        <Route path="prompts/:promptId/revisions/new" element={<Navigate to="../edit" replace />} />

        {/* Creating a prompt happens inside a folder, because the folder IS the
            namespace and A-021 makes it immutable — there is no later move. The
            folderless routes that used to live here defaulted the namespace to
            `workspace`, so a prompt begun from a folder page was filed somewhere
            else entirely; they redirect to the grid, where a folder gets picked
            first. */}
        <Route path="prompts/folder/:folderId/new" element={<PromptEditorPage />} />
        <Route path="prompts/new" element={<Navigate to="/app/prompts" replace />} />
        <Route path="prompts/new/wizard" element={<Navigate to="/app/prompts" replace />} />

        {/* Not lifecycle screens, but this is the only router mounted under
            /app — and its catch-all is what used to swallow both of these. */}
        <Route path="settings" element={<Navigate to="/app/settings/profile" replace />} />
        <Route path="settings/profile" element={<ProfilePage />} />
        <Route path="settings/providers" element={<ProvidersPage />} />
        <Route path="settings/keys" element={<ApiKeysPage />} />
        <Route path="settings/workspace" element={<WorkspaceMembersPage />} />
        {/* Keep direct bookmarks working while Settings owns these destinations. */}
        <Route path="account" element={<AccountPage />} />

        {/* Other routes */}
        {/* The playground, reachable from the sidebar with no prompt in hand. The
            per-prompt route above renders the same component; the difference is
            only where the prompt id comes from. */}
        <Route path="playground" element={<PlaygroundPage />} />
        {/* Per-app keys and the snippets that use them. Neither the playground
            nor an eval run needs anything from this page — those are recorded as
            internal and carry no credential at all. */}
        <Route path="keys" element={<Navigate to="/app/settings/keys" replace />} />
        {/* Members, the pending queue, and invitations now live in Settings. */}
        <Route path="workspace" element={<Navigate to="/app/settings/workspace" replace />} />
        <Route path="search" element={<PromptSearchPage />} />
        <Route path="imports/new" element={<ImportUploadPage />} />
        <Route path="imports/:batchId" element={<ImportReviewPage />} />
        <Route path="reviews" element={<ReviewQueuePage />} />
        <Route path="reviews/:reviewId" element={<ReviewDetailPage />} />
        {/* The standalone release form was a mock: it waited 440 ms, echoed its
            own input back and offered two hardcoded `rev_checkout_*` targets. A
            release now happens on the prompt's own Release tab, against the
            revision the rail has selected, so this redirects rather than 404s —
            `:revisionId` was in practice the prompt id (ReviewDetailPage passed
            `review.promptId`), which is what the tab needs anyway. */}
        <Route path="releases/:revisionId" element={<ReleaseRedirect />} />
        <Route path="providers" element={<Navigate to="/app/settings/providers" replace />} />
        <Route path="datasets" element={<DatasetPage />} />
        <Route path="datasets/:datasetId" element={<DatasetDetailPage />} />
        <Route path="labels" element={<LabelingPage />} />

        {/* Legacy redirects */}
        <Route path="vault/folder-1" element={<Navigate to="/app/prompts" replace />} />
        {/* These two named fixture prompts, which no real workspace has. They
            now land on the folder grid, which is where a stale bookmark should
            arrive: a redirect to a prompt id that does not exist answers
            not-found, and not-found is the same answer a private prompt gives. */}
        <Route path="vault/folder-1/customer-support" element={<Navigate to="/app/prompts" replace />} />
        <Route path="vault/folder-1/claim-screening" element={<Navigate to="/app/prompts" replace />} />
        <Route path="evaluation/review-queue" element={<Navigate to="/app/reviews" replace />} />
        <Route path="evaluation/datasets" element={<Navigate to="/app/datasets" replace />} />
        <Route path="evaluation/reports" element={<Navigate to="/app/prompts" replace />} />

        {/* Default fallback */}
        <Route path="*" element={<Navigate to="/app/prompts" replace />} />
      </Routes>
    </Suspense>
  );
}
