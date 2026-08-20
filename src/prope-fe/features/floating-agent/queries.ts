import { queryOptions } from '@tanstack/react-query';
import { getFloatingAgentEvents } from '@/features/floating-agent/api';

export const floatingAgentEventsOptions = queryOptions({
  queryKey: ['floating-agent', 'events'],
  queryFn: getFloatingAgentEvents,
  staleTime: 0,
  refetchInterval: (query) => query.state.data?.some((event) => event.type === 'progress') ? 1_000 : false,
});
