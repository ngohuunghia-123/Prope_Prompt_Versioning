import { useMemo, useState } from 'react';
import type { PromptRow, PromptStatus } from '@/features/registry/types';

export function useRegistryFilters(rows: PromptRow[]) {
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState<PromptStatus | 'all'>('all');
  const filteredRows = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    return rows.filter((row) => {
      const matchesStatus = status === 'all' || row.status === status;
      const searchable = [row.name, row.modelName, row.owner, ...row.tags].join(' ').toLocaleLowerCase();
      return matchesStatus && (!normalizedQuery || searchable.includes(normalizedQuery));
    });
  }, [query, rows, status]);
  return { query, setQuery, status, setStatus, filteredRows };
}
