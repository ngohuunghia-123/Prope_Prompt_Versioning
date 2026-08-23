import { z } from 'zod';
import type { Prompt } from '@/features/prompt-lifecycle/types';

/**
 * The eight colours a folder may take, in the order the server holds them.
 *
 * `default_folder_color` in `prope.prompt_registry.domain` indexes into the same
 * tuple with the same hash, so reordering this array here without reordering it
 * there repaints every folder that never picked a colour.
 */
export const FOLDER_COLORS = [
  '#6366f1',
  '#f59e0b',
  '#10b981',
  '#8b5cf6',
  '#ef4444',
  '#06b6d4',
  '#ec4899',
  '#14b8a6',
] as const;

/**
 * The colour a folder gets when nobody picked one. Ported from the server's.
 *
 * The `??` is `noUncheckedIndexedAccess` doing its job, not a real branch: the
 * modulo cannot leave the tuple. Indexing position 0 explicitly is what gives
 * the fallback a literal type instead of another `string | undefined`.
 */
export function folderColor(slug: string): string {
  let hash = 0;
  for (const character of slug) hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  return FOLDER_COLORS[hash % FOLDER_COLORS.length] ?? FOLDER_COLORS[0];
}

export const folderSchema = z.object({
  // The slug, which is also the registry namespace and the route segment. Named
  // `id` because that is what every consumer of this type already calls it.
  id: z.string(),
  name: z.string(),
  description: z.string(),
  color: z.string(),
  // Whether a row in `registry.folder` backs this card, or whether it is a
  // namespace observed on prompts with a capitalised slug for a name. Only the
  // second kind needs the "chưa đặt tên" treatment; both may be edited, because
  // PATCH upserts.
  declared: z.boolean(),
  promptCount: z.number().int().nonnegative(),
  approvedCount: z.number().int().nonnegative(),
  inReviewCount: z.number().int().nonnegative(),
  draftCount: z.number().int().nonnegative(),
  updatedAt: z.string(),
});

export type Folder = z.infer<typeof folderSchema>;

export interface FolderWithPrompts extends Folder {
  prompts: Prompt[];
}

/** `POST /api/v1/folders`. The slug is chosen once and never moves (A-021). */
export interface FolderCreateInput {
  slug: string;
  name: string;
  description: string;
  color: string;
  autoName?: boolean;
}

/**
 * `PATCH /api/v1/folders/{slug}`, which is also the verb that *declares* an
 * observed namespace. There is no slug field, for A-021's reason.
 */
export interface FolderUpdateInput {
  slug: string;
  name?: string;
  description?: string;
  color?: string;
}

export const MOCK_FOLDERS: Folder[] = [
  {
    id: 'general',
    name: 'General',
    description: 'General purpose prompts for various use cases',
    declared: true,
    color: '#6366f1',
    promptCount: 12,
    approvedCount: 8,
    inReviewCount: 2,
    draftCount: 2,
    updatedAt: '2026-08-10T14:30:00Z',
  },
  {
    id: 'marketing',
    name: 'Marketing',
    description: 'Prompts for marketing campaigns and content creation',
    declared: true,
    color: '#f59e0b',
    promptCount: 8,
    approvedCount: 5,
    inReviewCount: 1,
    draftCount: 2,
    updatedAt: '2026-08-12T09:15:00Z',
  },
  {
    id: 'technical',
    name: 'Technical',
    description: 'Technical documentation and code-related prompts',
    declared: true,
    color: '#10b981',
    promptCount: 15,
    approvedCount: 10,
    inReviewCount: 3,
    draftCount: 2,
    updatedAt: '2026-08-11T16:45:00Z',
  },
  {
    id: 'customer-support',
    name: 'Customer Support',
    description: 'Prompts for customer service and support workflows',
    declared: true,
    color: '#8b5cf6',
    promptCount: 20,
    approvedCount: 15,
    inReviewCount: 3,
    draftCount: 2,
    updatedAt: '2026-08-13T08:00:00Z',
  },
  {
    id: 'sales',
    name: 'Sales',
    description: 'Sales automation and lead qualification prompts',
    declared: true,
    color: '#ef4444',
    promptCount: 6,
    approvedCount: 4,
    inReviewCount: 1,
    draftCount: 1,
    updatedAt: '2026-08-09T11:20:00Z',
  },
  {
    id: 'analytics',
    name: 'Analytics',
    description: 'Data analysis and reporting prompts',
    declared: true,
    color: '#06b6d4',
    promptCount: 9,
    approvedCount: 6,
    inReviewCount: 2,
    draftCount: 1,
    updatedAt: '2026-08-12T15:00:00Z',
  },
];

export function getFolderById(id: string): Folder | undefined {
  return MOCK_FOLDERS.find((folder) => folder.id === id);
}
