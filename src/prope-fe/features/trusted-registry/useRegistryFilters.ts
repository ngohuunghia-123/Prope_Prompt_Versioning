import { useMemo, useState } from 'react';
import type { RegistryPrompt } from '@/features/trusted-registry/types';

function normalizeSearchText(value: string) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLocaleLowerCase();
}

export function useRegistryFilters(prompts: RegistryPrompt[]) {
  const [search, setSearch] = useState('');
  const [owner, setOwner] = useState('all');
  const [status, setStatus] = useState('all');
  const [access, setAccess] = useState('all');
  const visiblePrompts = useMemo(() => prompts.filter((prompt) => {
    const term = normalizeSearchText(search.trim());
    const searchable = normalizeSearchText([prompt.title, prompt.purpose, prompt.content, prompt.ownerName, prompt.modelName, ...prompt.tags].join(' '));
    return (!term || searchable.includes(term)) && (owner === 'all' || prompt.ownerName === owner) &&
      (status === 'all' || prompt.status === status) && (access === 'all' || prompt.accessLevel === access);
  }), [access, owner, prompts, search, status]);
  const filtered = Boolean(search.trim()) || [owner, status, access].some((value) => value !== 'all');
  const clear = () => { setSearch(''); setOwner('all'); setStatus('all'); setAccess('all'); };
  return { search, setSearch, owner, setOwner, status, setStatus, access, setAccess, visiblePrompts, filtered, clear };
}
