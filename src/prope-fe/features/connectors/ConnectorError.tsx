import { useTranslation } from 'react-i18next';
import { ApiError } from '@/lib/apiClient';

const errorKeys: Partial<Record<string, string>> = {
  invalid_canonical_xml: 'connector.invalidCanonicalXml',
  session_context_too_large: 'connector.sessionTooLarge',
  session_history_too_large: 'connector.sessionHistoryTooLarge',
  session_history_incomplete: 'connector.sessionHistoryIncomplete',
  session_history_invalid: 'connector.sessionHistoryIncomplete',
  session_history_unavailable: 'connector.sessionHistoryUnavailable',
  session_history_timeout: 'connector.sessionHistoryTimeout',
  session_history_pagination_unsupported: 'connector.sessionHistoryUnsupported',
};

export function ConnectorError({ error }: { error: unknown }) {
  const { t } = useTranslation();
  if (!error) return null;
  const messageKey = error instanceof ApiError ? errorKeys[error.code] : undefined;
  return <p role="alert" className="rounded-lg border border-danger-strong bg-danger p-3 text-danger-text">
    {messageKey ? t(messageKey) : t('connector.error', { code: error instanceof ApiError ? error.code : 'invalid_response' })}
    {error instanceof ApiError && error.requestId ? <span className="block">{t('connector.request', { id: error.requestId })}</span> : null}
  </p>;
}
