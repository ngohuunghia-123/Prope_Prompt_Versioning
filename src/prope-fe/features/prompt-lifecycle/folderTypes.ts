import { z } from 'zod';
import type { Prompt } from '@/features/prompt-lifecycle/types';

export const folderSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  color: z.string(),
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

export const MOCK_FOLDERS: Folder[] = [
  {
    id: 'general',
    name: 'General',
    description: 'General purpose prompts for various use cases',
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
