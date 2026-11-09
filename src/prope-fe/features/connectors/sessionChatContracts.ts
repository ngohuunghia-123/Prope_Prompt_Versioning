import { z } from 'zod';
import { conversationIdSchema, conversationTitleTargetSchema } from '@/features/connectors/contracts';

export const sessionMessageSchema = z.object({
  id: z.string().min(1).max(200), role: z.enum(['user', 'assistant']), text: z.string().max(1_000_000),
}).strict();
export const sessionSnapshotSchema = z.object({
  grant_id: z.string().uuid(), snapshot_id: z.string().uuid(), connection_id: z.string(),
  thread_id: conversationIdSchema, title: z.string().nullable(), host: z.literal('codex'),
  read_at: z.number(), has_content: z.boolean(), uncertain: z.boolean(),
}).strict();
export type SessionSnapshot = z.infer<typeof sessionSnapshotSchema>;
export const sessionBindingSchema = z.object({ provider_config_id: z.string().min(1).max(200).regex(/^[a-zA-Z0-9_:@.-]+$/), upstream_model: z.string().min(1).max(200) }).strict();
export type SessionBinding = z.infer<typeof sessionBindingSchema>;
const grantTarget = z.object({ grant_id: z.string().uuid() });
export const sessionChatRequestSchema = z.discriminatedUnion('operation', [
  conversationTitleTargetSchema.extend({ operation: z.literal('grant') }).strict(),
  z.object({ operation: z.literal('state') }).strict(),
  grantTarget.extend({ operation: z.literal('refresh') }).strict(),
  grantTarget.extend({ operation: z.literal('history') }).strict(),
  grantTarget.extend({ operation: z.literal('revoke') }).strict(),
  grantTarget.extend({ operation: z.literal('send'), snapshot_id: z.string().uuid(),
    expires_at: z.number().int().positive(),
    conversation_id: z.string().max(64).nullable(), text: z.string().min(1).max(4000),
    attachment: z.string().max(32768).nullable(), attachment_format: z.enum(['txt', 'md', 'markdown', 'json', 'yaml']),
  }).strict(),
  grantTarget.extend({ operation: z.literal('decide'), action_id: z.string().min(1).max(200), approve: z.boolean(),
    expires_at: z.number().int().positive(),
    edits: z.partialRecord(z.enum(['name', 'title']), z.string().max(200)).optional(),
  }).strict(),
  grantTarget.extend({ operation: z.literal('feedback'), message_id: z.string().max(200), rating: z.enum(['helpful', 'not_helpful']),
    reason: z.enum(['incorrect', 'unsupported_source', 'misunderstood', 'other']).optional(),
  }).strict(),
]);
