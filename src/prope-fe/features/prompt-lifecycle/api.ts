import { z } from 'zod';
import {
  callRecordSchema,
  evaluationWorkflowSchema,
  promptDetailSchema,
  promptEditorSchema,
  promptSchema,
  providerFormSchema,
  providerSchema,
  releaseFormSchema,
  reviewSchema,
  workflowActionSchema,
  type PromptEditorValues,
  type ProviderFormValues,
  type ReleaseFormValues,
  type WorkflowAction,
} from '@/features/prompt-lifecycle/types';
import { createEvaluationWorkflow } from '@/features/prompt-lifecycle/workflowData';

const wait = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

const prompts = [
  { id: 'checkout-assistant', title: 'Checkout assistant', modelName: 'commerce/checkout-assistant', owner: 'Linh Nguyễn', access: 'workspace', status: 'inUse', revision: 'r12', updatedAt: '2026-08-11T08:15:00+07:00', tags: ['commerce', 'production'] },
  { id: 'support-triage', title: 'Support triage', modelName: 'support/triage', owner: 'An Trần', access: 'private', status: 'inReview', revision: 'r8', updatedAt: '2026-08-11T07:20:00+07:00', tags: ['support', 'safety'] },
  { id: 'catalog-enrichment', title: 'Catalog enrichment', modelName: 'catalog/enrichment', owner: 'Mai Lê', access: 'workspace', status: 'approved', revision: 'r5', updatedAt: '2026-08-10T16:30:00+07:00', tags: ['catalog', 'structured'] },
  { id: 'launch-brief', title: 'Launch brief', modelName: 'marketing/launch-brief', owner: 'Minh Phạm', access: 'private', status: 'draft', revision: 'r3', updatedAt: '2026-08-10T10:45:00+07:00', tags: ['marketing'] },
] as const;

const revisions = [
  { id: 'rev_checkout_12', number: 'r12', status: 'inUse', author: 'Linh Nguyễn', createdAt: '2026-08-11T08:15:00+07:00', summary: 'Tighten checkout policy and structured handoff.', evalPassed: 18, evalTotal: 20, cost: 0.084 },
  { id: 'rev_checkout_11', number: 'r11', status: 'approved', author: 'Linh Nguyễn', createdAt: '2026-08-08T14:10:00+07:00', summary: 'Add fallback answer for upstream outages.', evalPassed: 17, evalTotal: 20, cost: 0.079 },
  { id: 'rev_checkout_10', number: 'r10', status: 'retired', author: 'Mai Lê', createdAt: '2026-08-01T09:20:00+07:00', summary: 'Initial approved checkout policy.', evalPassed: 16, evalTotal: 20, cost: 0.076 },
] as const;

const reviews = [
  { id: 'review-support-r8', promptId: 'support-triage', promptTitle: 'Support triage', revision: 'r8', owner: 'An Trần', submittedAt: '2026-08-11T07:20:00+07:00', summary: 'Escalate sensitive refunds and add JSON schema validation.', passed: 19, total: 20, candidateCost: 0.094, releasedCost: 0.081 },
  { id: 'review-catalog-r6', promptId: 'catalog-enrichment', promptTitle: 'Catalog enrichment', revision: 'r6', owner: 'Mai Lê', submittedAt: '2026-08-10T15:10:00+07:00', summary: 'Require normalized units and forbidden phrase assertions.', passed: 20, total: 20, candidateCost: 0.061, releasedCost: 0.058 },
] as const;

const providers = [
  { id: 'openai', name: 'OpenAI', models: ['gpt-5.2', 'gpt-5.2-mini'], state: 'connected', updatedAt: '2026-08-11T08:00:00+07:00' },
  { id: 'anthropic', name: 'Anthropic', models: ['claude-sonnet-4-5'], state: 'connected', updatedAt: '2026-08-09T11:40:00+07:00' },
] as const;

const calls = [
  { id: 'call_01', promptTitle: 'Checkout assistant', versionId: 'rev_checkout_12', consumer: 'checkout-web', timestamp: '2026-08-11T09:12:00+07:00', tokens: 1842, cost: 0.0184, outcome: 'success' },
  { id: 'call_02', promptTitle: 'Checkout assistant', versionId: 'rev_checkout_12', consumer: 'checkout-web', timestamp: '2026-08-11T09:08:00+07:00', tokens: 0, cost: 0, outcome: 'fallback' },
  { id: 'call_03', promptTitle: 'Catalog enrichment', versionId: 'rev_catalog_5', consumer: 'catalog-worker', timestamp: '2026-08-11T08:54:00+07:00', tokens: 2310, cost: 0.0221, outcome: 'success' },
] as const;

export async function getPrompts() { await wait(260); return z.array(promptSchema).parse(prompts); }
export async function getPrompt(promptId: string) {
  await wait(220);
  const prompt = prompts.find((item) => item.id === promptId) ?? prompts[0];
  const promptBody = `<system>\nYou are the checkout assistant. Follow the approved checkout policy.\n</system>\n\n<context>\nCustomer: {{customer_name}}\nQuestion: {{question}}\n</context>\n\n<instructions>\nReturn concise guidance and emit the required handoff object.\n</instructions>\n\n<output_format>\nReturn valid JSON matching the approved schema.\n</output_format>`;
  return promptDetailSchema.parse({ ...prompt, purpose: 'Guide checkout conversations while preserving policy and a structured handoff.', provider: 'OpenAI', providerModel: 'gpt-5.2', fallbackAnswer: 'Checkout support is temporarily unavailable. Please try again shortly.', promptBody, revisions });
}
export async function getReviews() { await wait(240); return z.array(reviewSchema).parse(reviews); }
export async function getReview(reviewId: string) { await wait(220); return reviewSchema.parse(reviews.find((item) => item.id === reviewId) ?? reviews[0]); }
export async function getProviders() { await wait(200); return z.array(providerSchema).parse(providers); }
export async function getCallRecords() { await wait(230); return z.array(callRecordSchema).parse(calls); }

export async function savePrompt(values: PromptEditorValues) { await wait(420); return promptEditorSchema.parse(values); }
export async function startEvaluation(values: PromptEditorValues) {
  await wait(700);
  const parsed = promptEditorSchema.parse(values);
  window.sessionStorage.setItem('prope.mock-evaluation-started', String(Date.now()));
  return parsed;
}
export async function getEvaluationWorkflow(promptId: string) {
  await wait(180);
  const startedAt = Number(window.sessionStorage.getItem('prope.mock-evaluation-started'));
  const running = Number.isFinite(startedAt) && Date.now() - startedAt < 1400;
  if (!running) window.sessionStorage.removeItem('prope.mock-evaluation-started');
  return evaluationWorkflowSchema.parse(createEvaluationWorkflow(promptId, running));
}
export async function submitWorkflowAction(input: WorkflowAction) { await wait(360); return workflowActionSchema.parse(input); }
export async function decideReview(input: { reviewId: string; decision: 'approve' | 'changes' }) { await wait(360); return z.object({ reviewId: z.string(), decision: z.enum(['approve', 'changes']) }).parse(input); }
export async function saveProvider(values: ProviderFormValues) { await wait(400); return providerFormSchema.parse(values); }
export async function releaseRevision(values: ReleaseFormValues) { await wait(440); return releaseFormSchema.parse(values); }
