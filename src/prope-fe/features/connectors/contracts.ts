import { z } from 'zod';

const id = z.string().min(1).max(200).regex(/^[a-zA-Z0-9_:@.-]+$/);
export const sourceSchema = z.object({
  source: z.string().min(1).max(32768),
  format: z.enum(['txt', 'markdown', 'xml']).default('markdown'),
  host: z.enum(['codex', 'claude-code', 'other']),
});
export const captureSchema = sourceSchema.strict();
export const revisionProposalSchema = sourceSchema.extend({ prompt_id: id, base_version_id: id }).strict();
export const evaluationProposalSchema = z.object({
  prompt_id: id, original_version_id: id, candidate_version_id: id, dataset_id: id,
}).strict();
export const proposalSchema = z.discriminatedUnion('kind', [
  captureSchema.extend({ kind: z.literal('capture') }),
  revisionProposalSchema.extend({ kind: z.literal('revision') }),
  evaluationProposalSchema.extend({ kind: z.literal('evaluation') }),
]);
export type ProposalInput = z.infer<typeof proposalSchema>;
export const pendingSchema = z.object({
  id: z.string(), connection_id: z.string(), namespace: z.string(), expires_at: z.number(),
  input: proposalSchema, status: z.enum(['pending', 'saved', 'uncertain']),
  result: z.unknown().optional(),
});
export type Pending = z.infer<typeof pendingSchema>;
export const destinationSchema = z.object({
  prompt_id: z.string(), namespace: id, name: id,
  title: z.string().min(1).max(200), base_version_id: z.string(),
  provider_config_id: z.string().min(1), upstream_model: z.string().min(1).max(200),
  change_summary: z.string().min(1).max(2000),
}).strict();
export type Destination = z.infer<typeof destinationSchema>;
export const conversationIdSchema = z.string().min(1).max(128).regex(/^[a-zA-Z0-9][a-zA-Z0-9_-]*$/);
export const conversationObservationSchema = z.object({
  thread_id: conversationIdSchema, first_seen: z.number(), last_seen: z.number(),
  source: z.enum(['mcp_metadata_thread_id', 'user_selected_codex_thread']),
});
export type ConversationObservation = z.infer<typeof conversationObservationSchema>;
export const conversationTitleTargetSchema = z.object({ connection_id: z.string().regex(/^[A-F0-9]{8}$/), thread_id: conversationIdSchema }).strict();
export const conversationTitleSchema = z.object({
  thread_id: conversationIdSchema, title: z.string().max(1000).nullable(),
  source: z.literal('codex_thread_read'), checked_at: z.number(),
}).strict();
export type ConversationTitle = z.infer<typeof conversationTitleSchema>;
export const agentConnectionSchema = z.object({
  connection_id: z.string().regex(/^[A-F0-9]{8}$/), client_name: z.string().nullable(),
  status: z.enum(['pending', 'awaiting_client', 'connected']), namespace: z.string().nullable(),
  heartbeat_at: z.number().nullable(),
  conversations: z.array(conversationObservationSchema).max(32).default([]),
  conversation_history_limited: z.boolean().default(false),
});
export const agentCheckSchema = z.object({ connection_id: z.string().regex(/^[A-F0-9]{8}$/) }).strict();
export const agentCheckResultSchema = agentCheckSchema.extend({ heartbeat_at: z.number() });
export const webviewRequestSchema = z.object({
  id: z.string().uuid(),
  action: z.enum(['state', 'connect', 'pair', 'disconnect', 'configuration', 'agent_connections', 'check_agent', 'choose_conversation', 'conversation_title', 'session_chat', 'manage', 'read', 'preview', 'save', 'stage_evaluation', 'evaluate', 'reject', 'capture_direct', 'stage_revision', 'stage_comparison', 'attach_datasets', 'create_dataset', 'run_revision', 'start_improvement', 'review_improvement']),
  payload: z.unknown().optional(),
}).strict();
export const connectorStateSchema = z.object({
  connected: z.boolean(), workspace_id: z.string().nullable(),
  workspace_name: z.string().nullable(), proposals: z.array(pendingSchema),
});
export type ConnectorState = z.infer<typeof connectorStateSchema>;
export const previewSchema = z.object({
  proposal_id: z.string(), digest: z.string(), body: z.string(), original: z.string(),
  base_body: z.string(), base_fingerprint: z.string(), destination: destinationSchema,
  model: z.string().nullable(), schema_version: z.string().nullable(),
});
export type Preview = z.infer<typeof previewSchema>;
