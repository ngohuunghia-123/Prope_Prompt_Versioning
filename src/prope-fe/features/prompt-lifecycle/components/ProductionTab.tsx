import { LogsTab } from '@/features/prompt-lifecycle/components/LogsTab';

interface ProductionTabProps {
  promptId: string;
  revisionId: string | null;
  revisionLabel: string | null;
}

export function ProductionTab({ promptId, revisionId, revisionLabel }: ProductionTabProps) {
  return <LogsTab promptId={promptId} revisionId={revisionId} revisionLabel={revisionLabel} />;
}
