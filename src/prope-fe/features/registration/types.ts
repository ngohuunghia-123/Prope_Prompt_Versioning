import { z } from 'zod';
import { promptAccessSchema, promptFormSchema } from '@/features/preservation/types';

export const registrationFormSchema = promptFormSchema;
export type RegistrationFormValues = z.infer<typeof registrationFormSchema>;
export type RegistrationAccess = z.infer<typeof promptAccessSchema>;

export const registrationMetadataSchema = z.object({
  owners: z.array(z.object({ id: z.string(), name: z.string(), role: z.enum(['owner', 'product', 'engineer']) })),
  providers: z.array(z.object({ id: z.string(), name: z.string(), models: z.array(z.string()) })),
});

export type RegistrationMetadata = z.infer<typeof registrationMetadataSchema>;
