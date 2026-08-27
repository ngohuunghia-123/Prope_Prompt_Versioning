import { useState } from 'react';

import type { UsageProfile, UsageProfileAxis } from '@/features/prompt-lifecycle/readinessTypes';

const AXES: UsageProfileAxis[] = ['audience', 'untrusted_input', 'acts', 'sensitivity'];

function storageKey(promptId: string, versionId: string) {
  return `prope:usage-profile-wizard:${promptId}:${versionId}`;
}

function storedAxes(promptId: string, versionId: string): UsageProfileAxis[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(storageKey(promptId, versionId)) ?? '[]');
    return Array.isArray(parsed) ? parsed.filter((value): value is UsageProfileAxis => AXES.includes(value as UsageProfileAxis)) : [];
  } catch {
    return [];
  }
}

export function useUsageProfileWizardProgress(promptId: string, versionId: string, profile?: UsageProfile) {
  const [answered, setAnswered] = useState<UsageProfileAxis[]>(() => storedAxes(promptId, versionId));
  const completed = new Set([...answered, ...AXES.filter((axis) => profile?.[axis] !== 'undeclared')]);
  const firstIncomplete = AXES.findIndex((axis) => !completed.has(axis));
  const markAnswered = (axis: UsageProfileAxis) => {
    setAnswered((current) => {
      const next = current.includes(axis) ? current : [...current, axis];
      localStorage.setItem(storageKey(promptId, versionId), JSON.stringify(next));
      return next;
    });
  };
  return { firstIncomplete, markAnswered };
}
