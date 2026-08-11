import { z } from 'zod';
import { promptAccessSchema } from '@/features/preservation/types';

export const accessRecordSchema = z.object({
  promptId: z.string().min(1),
  permission: z.enum(['manage', 'denied']),
  access: promptAccessSchema,
  ownerId: z.string().min(1),
  ownerName: z.string().min(1),
  availableOwners: z.array(z.object({ id: z.string().min(1), name: z.string().min(1), role: z.string().min(1) })),
  grants: z.array(z.object({
    id: z.string().min(1), userId: z.string().min(1), userName: z.string().min(1), level: z.enum(['viewer', 'editor']),
  })),
  activity: z.array(z.object({
    id: z.string().min(1), kind: z.enum(['accessChanged', 'granted', 'revoked', 'ownershipTransferred']),
    actorName: z.string().min(1), subjectName: z.string().nullable(), value: z.string().nullable(), occurredAt: z.string(),
  })),
  lastActivityAt: z.string(),
});

export const accessFormSchema = z.object({ access: promptAccessSchema });
export const transferFormSchema = z.object({ newOwnerId: z.string().min(1, 'newOwner') });
export const grantFormSchema = z.object({ userId: z.string().min(1, 'userId'), level: z.enum(['viewer', 'editor']) });

export type AccessRecord = z.infer<typeof accessRecordSchema>;
export type AccessFormValues = z.infer<typeof accessFormSchema>;
export type TransferFormValues = z.infer<typeof transferFormSchema>;
export type GrantFormValues = z.infer<typeof grantFormSchema>;
