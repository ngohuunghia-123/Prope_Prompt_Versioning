import { z } from 'zod';
import { RevisionWorkspace } from '@/features/connectors/RevisionWorkspace';
import { ConnectorError } from '@/features/connectors/ConnectorError';

export function SavedRevisionTools({ result }: { result: unknown }) {
  const parsed = z.object({ prompt_id: z.string(), version_id: z.string() }).safeParse(result);
  return parsed.success ? <RevisionWorkspace promptId={parsed.data.prompt_id} versionId={parsed.data.version_id} /> : <ConnectorError error={new Error('invalid_receipt')} />;
}
