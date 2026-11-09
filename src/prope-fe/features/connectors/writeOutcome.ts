import { ApiError } from '@/lib/apiClient';

const safeToRetry = new Set(['cancelled', 'base_changed', 'configuration_changed', 'dataset_required', 'invalid_evidence', 'invalid_base',
  'workspace_required', 'password_change_required', 'session_required', 'scope_denied', 'permission_denied', 'not_found',
  'action_denied', 'read_denied', 'operation_in_progress', 'validation_failed', 'invalid_request']);

export function isUncertainWrite(error: unknown) {
  if (!error) return false;
  return !(error instanceof ApiError) || error.status >= 500 || !safeToRetry.has(error.code);
}
