import { z } from 'zod';

export const similarCheckFormSchema = z.object({
  title: z.string().trim().min(3, 'title'),
  content: z.string().trim().min(20, 'content'),
});

export const similarMatchSchema = z.object({
  id: z.string().min(1), title: z.string().min(1), purpose: z.string().min(1), score: z.number().min(0).max(100), ownerName: z.string().min(1),
});

export const similarCheckResultSchema = z.object({ matches: z.array(similarMatchSchema) });

export type SimilarCheckFormValues = z.infer<typeof similarCheckFormSchema>;
export type SimilarCheckResult = z.infer<typeof similarCheckResultSchema>;
