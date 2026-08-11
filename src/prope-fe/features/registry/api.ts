import type { PromptRow } from '@/features/registry/types';

const mockPrompts: PromptRow[] = [
  { id: 'checkout', name: 'Checkout assistant', modelName: 'ecom/checkout-assistant', owner: 'Linh Nguyễn', revision: 'v2.4', status: 'inUse', tags: ['commerce'], updatedAt: '2026-08-09T08:00:00Z' },
  { id: 'support', name: 'Support triage', modelName: 'care/support-triage', owner: 'An Trần', revision: 'v1.8', status: 'inReview', tags: ['customer care'], updatedAt: '2026-08-08T08:00:00Z' },
  { id: 'catalog', name: 'Catalog enrichment', modelName: 'content/catalog-enrichment', owner: 'Mai Lê', revision: 'v3.1', status: 'approved', tags: ['content'], updatedAt: '2026-08-07T08:00:00Z' },
  { id: 'launch', name: 'Launch brief', modelName: 'marketing/launch-brief', owner: 'Minh Phạm', revision: 'v0.6', status: 'draft', tags: ['marketing'], updatedAt: '2026-08-05T08:00:00Z' },
];

export async function listPrompts(): Promise<PromptRow[]> {
  await new Promise((resolve) => window.setTimeout(resolve, 420));
  return structuredClone(mockPrompts);
}
