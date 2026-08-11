export type PromptStatus = 'draft' | 'inReview' | 'approved' | 'inUse' | 'retired';

export interface PromptRow {
  id: string;
  name: string;
  modelName: string;
  owner: string;
  revision: string;
  status: PromptStatus;
  tags: string[];
  updatedAt: string;
}
