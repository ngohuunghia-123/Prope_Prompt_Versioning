import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { promptLogsOptions } from '@/features/prompt-lifecycle/queries';
import type { PromptLog } from '@/features/prompt-lifecycle/types';

const PAGE_SIZE = 6;

export function usePromptLogs(promptId: string, revisionId: string) {
  const query = useQuery(promptLogsOptions(promptId));
  const [search, setSearch] = useState('');
  const [technology, setTechnology] = useState('all');
  const [type, setType] = useState('all');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<PromptLog>();

  useEffect(() => {
    setPage(1);
    setSelected(undefined);
  }, [revisionId]);

  const normalizedSearch = search.trim().toLowerCase();
  const filtered = (query.data ?? []).filter((log) =>
    log.revisionId === revisionId
    && (technology === 'all' || log.technology === technology)
    && (type === 'all' || log.type === type)
    && (!normalizedSearch || `${log.id} ${log.description} ${log.model}`.toLowerCase().includes(normalizedSearch)),
  );
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const visibleLogs = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const updateSearch = (value: string) => { setSearch(value); setPage(1); };
  const updateTechnology = (value: string) => { setTechnology(value); setPage(1); };
  const updateType = (value: string) => { setType(value); setPage(1); };

  return {
    query, search, technology, type, currentPage, pageCount, visibleLogs, selected,
    setSearch: updateSearch, setTechnology: updateTechnology, setType: updateType,
    previousPage: () => setPage((value) => Math.max(1, value - 1)),
    nextPage: () => setPage((value) => Math.min(pageCount, value + 1)),
    selectLog: setSelected,
    closeDetail: () => setSelected(undefined),
  };
}
