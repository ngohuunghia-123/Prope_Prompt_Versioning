import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { applyMockPromptStatus, promptKeys, readMockPromptsSnapshot } from '@/features/preservation/queries';
import {
  evaluationRunSchema,
  evaluationSuiteFormSchema,
  evaluationWorkspaceSchema,
  testInputFormSchema,
  type EvaluationWorkspace,
  type EvaluationSuiteFormValues,
  type TestInputFormValues,
} from '@/features/evaluation/types';

const wait = () => new Promise((resolve) => window.setTimeout(resolve, 420));
const workspaces = new Map<string, EvaluationWorkspace>();

function createWorkspace(promptId: string) {
  const makeInputs = (suiteId: string, count: number) => Array.from({ length: count }, (_, index) => ({
    id: `${suiteId}-input-${index + 1}`,
    name: `Deterministic case ${index + 1}`,
    content: `Enterprise prompt test payload ${index + 1} with fixed evidence and expected behavior.`,
    assertionType: 'contains' as const,
    expected: index === 9 ? 'INSUFFICIENT_EVIDENCE' : 'EVIDENCE',
  }));
  const primaryId = `${promptId}-accuracy`;
  const formatId = `${promptId}-format`;
  return evaluationWorkspaceSchema.parse({
    promptId,
    suiteName: 'accuracy',
    suiteVersion: 2,
    outputModality: 'text',
    revisionNumber: readMockPromptsSnapshot().find((prompt) => prompt.id === promptId)?.currentRevision ?? 1,
    revisionSummary: 'Làm rõ tiêu chí và định dạng đầu ra',
    inputs: promptId === 'empty-evidence' ? [] : makeInputs(primaryId, 10),
    latestRun: null,
    additionalSuites: [{ id: formatId, name: 'format', version: 1, outputModality: 'structured', inputs: makeInputs(formatId, 10), latestRun: null }],
    warningAccepted: false,
    readyForReview: false,
  });
}

async function readWorkspace(promptId: string) {
  await wait();
  if (!promptId || promptId === 'evaluation-error') throw new Error('EVALUATION_NOT_FOUND');
  const workspace = workspaces.get(promptId) ?? createWorkspace(promptId);
  workspaces.set(promptId, workspace);
  return evaluationWorkspaceSchema.parse(workspace);
}

async function addTestInput(input: TestInputFormValues & { promptId: string; suiteId: string }) {
  await wait();
  const values = testInputFormSchema.parse(input);
  const workspace = workspaces.get(input.promptId) ?? createWorkspace(input.promptId);
  const primarySuiteId = `${input.promptId}-accuracy`;
  const suite = input.suiteId === primarySuiteId ? null : workspace.additionalSuites.find((item) => item.id === input.suiteId);
  const currentInputs = suite?.inputs ?? workspace.inputs;
  if (currentInputs.length >= 20) throw new Error('EVALUATION_INPUT_LIMIT');
  const newInput = { id: `${input.suiteId}-input-${Date.now()}`, ...values };
  const updated = evaluationWorkspaceSchema.parse({
    ...workspace,
    inputs: input.suiteId === primarySuiteId ? [...workspace.inputs, newInput] : workspace.inputs,
    latestRun: input.suiteId === primarySuiteId ? null : workspace.latestRun,
    additionalSuites: workspace.additionalSuites.map((item) => item.id === input.suiteId ? { ...item, inputs: [...item.inputs, newInput], latestRun: null } : item),
    warningAccepted: false,
    readyForReview: false,
  });
  workspaces.set(input.promptId, updated);
  return updated;
}

async function createSuite(input: EvaluationSuiteFormValues & { promptId: string }) {
  await wait();
  const values = evaluationSuiteFormSchema.parse(input);
  const workspace = workspaces.get(input.promptId) ?? createWorkspace(input.promptId);
  if ([workspace.suiteName, ...workspace.additionalSuites.map((suite) => suite.name)].some((name) => name.toLocaleLowerCase() === values.name.toLocaleLowerCase())) throw new Error('EVALUATION_SUITE_EXISTS');
  const id = `${input.promptId}-${values.name.toLocaleLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
  const updated = evaluationWorkspaceSchema.parse({ ...workspace, additionalSuites: [...workspace.additionalSuites, { id, name: values.name, version: 1, outputModality: values.outputModality, inputs: [], latestRun: null }], readyForReview: false });
  workspaces.set(input.promptId, updated);
  return updated;
}

async function createSuiteVersion(input: { promptId: string; suiteId: string }) {
  await wait();
  const workspace = workspaces.get(input.promptId) ?? createWorkspace(input.promptId);
  const primarySuiteId = `${input.promptId}-accuracy`;
  const additionalExists = workspace.additionalSuites.some((suite) => suite.id === input.suiteId);
  if (input.suiteId !== primarySuiteId && !additionalExists) throw new Error('EVALUATION_SUITE_NOT_FOUND');
  const updated = evaluationWorkspaceSchema.parse({
    ...workspace,
    suiteVersion: input.suiteId === primarySuiteId ? workspace.suiteVersion + 1 : workspace.suiteVersion,
    latestRun: input.suiteId === primarySuiteId ? null : workspace.latestRun,
    additionalSuites: workspace.additionalSuites.map((suite) => suite.id === input.suiteId ? { ...suite, version: suite.version + 1, latestRun: null } : suite),
    warningAccepted: false, readyForReview: false,
  });
  workspaces.set(input.promptId, updated);
  return updated;
}

function buildRun(suiteId: string, inputs: EvaluationWorkspace['inputs'], hasBaseline: boolean, hasDispatchError: boolean, costDelta: number) {
  const results = inputs.map((input, index) => ({
    inputId: input.id,
    baselineOutput: hasBaseline ? (index === 0 ? 'Baseline output with mixed evidence.' : 'Baseline output for the deterministic case.') : null,
    candidateOutput: index === 0 ? 'Candidate output with direct evidence.' : 'Candidate output matching the deterministic assertion.',
    outcome: hasDispatchError && index === 0 ? 'error' as const : index === inputs.length - 1 ? 'fail' as const : 'pass' as const,
  }));
  const deltaUnavailableReason = hasDispatchError ? 'incompleteRun' as const : hasBaseline ? null : 'firstRelease' as const;
  return evaluationRunSchema.parse({
    id: `${suiteId}-run-${Date.now()}`, completedAt: new Date().toISOString(), results,
    tokens: { baseline: deltaUnavailableReason ? null : 840, candidate: 1010, delta: deltaUnavailableReason ? null : 20.2 },
    cost: { baseline: deltaUnavailableReason ? null : 0.024, candidate: 0.031, delta: deltaUnavailableReason ? null : costDelta },
    hasCostWarning: !deltaUnavailableReason && costDelta >= 20,
    requiresAcknowledgement: results.some((result) => result.outcome === 'fail'), deltaUnavailableReason,
  });
}

async function runComparison(promptId: string) {
  await wait();
  const workspace = workspaces.get(promptId) ?? createWorkspace(promptId);
  if (promptId === 'evaluation-failure') throw new Error('EVALUATION_FAILED');
  if (workspace.inputs.length > 20 || workspace.additionalSuites.some((suite) => suite.inputs.length > 20)) throw new Error('EVALUATION_SUITE_SIZE');
  const hasBaseline = readMockPromptsSnapshot().find((prompt) => prompt.id === promptId)?.releasedVersionId !== null;
  const hasDispatchError = promptId === 'evaluation-error-case';
  const run = workspace.inputs.length ? buildRun(`${promptId}-accuracy`, workspace.inputs, hasBaseline, hasDispatchError, 29.2) : null;
  const updated = evaluationWorkspaceSchema.parse({ ...workspace, latestRun: run, additionalSuites: workspace.additionalSuites.map((suite) => ({ ...suite, latestRun: suite.inputs.length ? buildRun(suite.id, suite.inputs, hasBaseline, hasDispatchError, suite.name === 'format' ? 6.2 : 12.4) : null })), warningAccepted: false, readyForReview: false });
  workspaces.set(promptId, updated);
  return updated;
}

async function markReady(promptId: string) {
  await wait();
  const workspace = workspaces.get(promptId) ?? createWorkspace(promptId);
  const suites = [{ inputs: workspace.inputs, latestRun: workspace.latestRun }, ...workspace.additionalSuites];
  const complete = suites.every((suite) => suite.inputs.length === 0 || suite.latestRun?.results.length === suite.inputs.length);
  if (!complete) throw new Error('EVALUATION_INCOMPLETE');
  const updated = evaluationWorkspaceSchema.parse({ ...workspace, warningAccepted: suites.some((suite) => suite.latestRun?.requiresAcknowledgement), readyForReview: true });
  workspaces.set(promptId, updated);
  applyMockPromptStatus(promptId, 'inReview');
  return updated;
}

export const evaluationKeys = { detail: (promptId: string) => ['evaluation-evidence', promptId] as const };
export const evaluationOptions = (promptId: string) => queryOptions({ queryKey: evaluationKeys.detail(promptId), queryFn: () => readWorkspace(promptId) });

function useWorkspaceMutation<TInput>(mutationFn: (input: TInput) => Promise<EvaluationWorkspace>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: (workspace) => { queryClient.setQueryData(evaluationKeys.detail(workspace.promptId), workspace); void queryClient.invalidateQueries({ queryKey: promptKeys.all }); void queryClient.invalidateQueries({ queryKey: ['review-tasks'] }); void queryClient.invalidateQueries({ queryKey: ['review-workspace', workspace.promptId] }); },
  });
}

export function useAddTestInput() { return useWorkspaceMutation(addTestInput); }
export function useCreateSuite() { return useWorkspaceMutation(createSuite); }
export function useCreateSuiteVersion() { return useWorkspaceMutation(createSuiteVersion); }
export function useRunComparison() { return useWorkspaceMutation(runComparison); }
export function useMarkEvidenceReady() { return useWorkspaceMutation(markReady); }

export function readEvaluationReviewSummary(promptId: string) {
  const workspace = workspaces.get(promptId);
  if (!workspace) return [];
  const suites = [{ name: workspace.suiteName, version: workspace.suiteVersion, modality: workspace.outputModality, run: workspace.latestRun }, ...workspace.additionalSuites.map((suite) => ({ name: suite.name, version: suite.version, modality: suite.outputModality, run: suite.latestRun }))];
  return suites.map((suite) => ({
    name: suite.name, version: suite.version, modality: suite.modality,
    passed: suite.run?.results.filter((result) => result.outcome === 'pass').length ?? 0,
    failed: suite.run?.results.filter((result) => result.outcome === 'fail').length ?? 0,
    errored: suite.run?.results.filter((result) => result.outcome === 'error').length ?? 0,
    costDelta: suite.run?.cost.delta ?? null,
  }));
}
