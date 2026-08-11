import { queryOptions } from '@tanstack/react-query';
import { listPrompts } from '@/features/registry/api';

export const registryKeys = { all: ['registry', 'prompts'] as const };

export const promptListOptions = queryOptions({
  queryKey: registryKeys.all,
  queryFn: listPrompts,
});
