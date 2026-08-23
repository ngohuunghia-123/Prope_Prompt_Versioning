import { useQuery } from '@tanstack/react-query';

import { readChatPipeline } from '@/features/chat/api';
import type { Pipeline } from '@/features/chat/types';

/**
 * The pipeline shape, fetched once per session and never revalidated.
 *
 * It is a build-time constant on the server — derived from the tool catalogue,
 * identical for every actor in every workspace — so `staleTime: Infinity` is a
 * statement of fact rather than a tuning choice. Every caller shares one request
 * through the query key.
 *
 * **Two places need it and only one of them is the graph.** The trace list needs
 * it too, to translate an agent name into Vietnamese: the alternative was a rule
 * in this client that says *the supervisor's label depends on its action* — the
 * exact piece of server knowledge that, copied here, goes stale the first time
 * somebody changes the pipeline and nothing fails.
 */
export function usePipeline(): Pipeline | undefined {
  return useQuery({
    queryKey: ['chat', 'pipeline'],
    queryFn: readChatPipeline,
    staleTime: Infinity,
    gcTime: Infinity,
  }).data;
}
