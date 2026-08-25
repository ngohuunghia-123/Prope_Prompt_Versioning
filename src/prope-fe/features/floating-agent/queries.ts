import { queryOptions } from '@tanstack/react-query';
import { getAgentRun, getFloatingAgentEvents } from '@/features/floating-agent/api';

export const floatingAgentEventsOptions = queryOptions({
  queryKey: ['floating-agent', 'events'],
  queryFn: getFloatingAgentEvents,
  staleTime: 0,
  refetchInterval: (query) => query.state.data?.some((event) => event.type === 'progress') ? 2_000 : 10_000,
  refetchOnReconnect: true,
  refetchOnWindowFocus: true,
});

export const agentRunOptions = (runId: string) => queryOptions({
  queryKey: ['floating-agent', 'run', runId],
  queryFn: () => getAgentRun(runId),
  staleTime: 2_000,
});
