import { z } from 'zod';
import { ApiError, apiRequest } from '@/lib/apiClient';
import { callHost } from '@/features/connectors/bridge';
import { agentCheckResultSchema, agentConnectionSchema, connectorStateSchema, conversationTitleSchema, previewSchema, type Destination } from '@/features/connectors/contracts';
import { promptReadSchema, revisionReadSchema, revisionSummaryReadSchema } from '@/features/prompt-lifecycle/types';
import { caseResultSchema, evalRunSchema } from '@/features/prompt-lifecycle/evalTypes';
export const getFolders = () => apiRequest('/api/v1/folders', { schema: z.array(z.object({ slug: z.string(), name: z.string() })) });

export const getConnectorState = async () => connectorStateSchema.parse(await callHost('state'));
export const getAgentConnections = async () => z.array(agentConnectionSchema).parse(await callHost('agent_connections'));
export const checkAgentConnection = async (connectionId: string) => agentCheckResultSchema.parse(await callHost('check_agent', { connection_id: connectionId }));
let titleQueue = Promise.resolve();
let queuedTitles = 0;
export const getConversationTitle = async (connectionId: string, threadId: string) => {
  if (queuedTitles >= 32) throw new ApiError(429, 'operation_in_progress', 'operation_in_progress');
  queuedTitles += 1;
  const result = titleQueue.then(() => callHost('conversation_title', { connection_id: connectionId, thread_id: threadId }));
  titleQueue = result.then(() => undefined, () => undefined);
  try { return conversationTitleSchema.parse(await result); } finally { queuedTitles -= 1; }
};
export const chooseConversation = (connectionId: string) => callHost('choose_conversation', { connection_id: connectionId });
export const getPrompts = () => apiRequest('/api/v1/prompts?limit=200', { schema: z.array(promptReadSchema) });
export const getPrompt = (id: string) => apiRequest(`/api/v1/prompts/${encodeURIComponent(id)}`, { schema: promptReadSchema });
export const getRevisions = (id: string) => apiRequest(`/api/v1/prompts/${encodeURIComponent(id)}/revisions`, { schema: z.array(revisionSummaryReadSchema) });
export const getRevision = (id: string) => apiRequest(`/api/v1/revisions/${encodeURIComponent(id)}`, { schema: revisionReadSchema });
export const getProviders = () => apiRequest('/api/v1/providers', { schema: z.array(z.object({ provider_config_id: z.string(), display_name: z.string() })) });
export const getAttachments = (id: string) => apiRequest(`/api/v1/prompts/${encodeURIComponent(id)}/dataset-attachments`, { schema: z.array(z.object({ dataset_id: z.string(), dataset: z.object({ name: z.string(), case_count: z.number() }).nullable() })) });
export const preparePreview = async (proposalId: string, destination: Destination) => previewSchema.parse(await callHost('preview', { proposal_id: proposalId, destination }));
export const savePreview = (proposalId: string, digest: string) => callHost('save', { proposal_id: proposalId, digest });
export const pairSchema = z.object({ prompt_id: z.string(), original_run_id: z.string(), candidate_run_id: z.string(), suite_id: z.string() });
export type RunPair = z.infer<typeof pairSchema>;
export const comparisonSchema = pairSchema.extend({ original: evalRunSchema, candidate: evalRunSchema, original_cases: z.array(caseResultSchema), candidate_cases: z.array(caseResultSchema), comparable: z.boolean(), withheld_reason: z.string().nullable(), metric_kind: z.literal('deterministic'), provider_config_id: z.string(), upstream_model: z.string(), parameters: z.record(z.string(), z.unknown()) });
export const getComparison = (pair: RunPair) => apiRequest(`/api/v1/prompts/${encodeURIComponent(pair.prompt_id)}/eval-comparisons?${new URLSearchParams({ original_run_id: pair.original_run_id, candidate_run_id: pair.candidate_run_id })}`, { schema: comparisonSchema });
