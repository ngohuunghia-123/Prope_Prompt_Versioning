import { useTranslation } from 'react-i18next';
import { StatusBadge } from '@/components/StatusBadge';
import type { Prompt } from '@/features/prompt-lifecycle/types';

const toneByStatus: Record<Prompt['status'], 'active' | 'pending' | 'error' | 'disabled'> = {
  draft: 'disabled',
  inReview: 'pending',
  approved: 'active',
  inUse: 'active',
  retired: 'disabled',
};

export interface LifecycleStatusProps { status: Prompt['status']; }

export function LifecycleStatus({ status }: LifecycleStatusProps) {
  const { t } = useTranslation();
  return <StatusBadge tone={toneByStatus[status]}>{t(`status.${status}`)}</StatusBadge>;
}
