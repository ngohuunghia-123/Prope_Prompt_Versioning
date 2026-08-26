import { z } from 'zod';
import { SLUG_PATTERN } from '@/lib/slugify';
import { parseXmlBlocks } from '@/features/prompt-lifecycle/xmlBlocks';
import { routerComboEntrySchema } from '@/features/prompt-lifecycle/routerComboTypes';

export const promptStatusSchema = z.enum(['draft', 'inReview', 'approved', 'inUse', 'retired']);

export const revisionSchema = z.object({
  id: z.string(),
  number: z.string(),
  status: promptStatusSchema,
  author: z.string(),
  authorEmail: z.string().email().nullable().optional(),
  createdAt: z.string(),
  summary: z.string(),
  evalPassed: z.number().int().nonnegative(),
  evalTotal: z.number().int().positive(),
  cost: z.number().nonnegative(),
  promptBody: z.string(),
  // The upstream binding this revision carries, so the playground can seed its
  // model and parameter controls from the revision rather than from a default
  // nobody chose. Defaulted rather than required: the list endpoint omits them
  // (a revision summary has no body and no parameters), and the mock arm has
  // never had them at all.
  providerConfigId: z.string().default(''),
  upstreamModel: z.string().default(''),
  // The frozen route this revision was created against — ADR-0069. A revision
  // binds a pair or a route, never both, so an empty `route` and an empty
  // `providerConfigId` together mean unbound, and exactly one of them is
  // filled otherwise.
  //
  // `routeComboName` is the name AS IT WAS at create. It may no longer match
  // any combo in Settings, and that is the point rather than a staleness bug:
  // the rungs below it are what the gateway will actually walk.
  routeComboId: z.string().default(''),
  routeComboName: z.string().default(''),
  route: z.array(routerComboEntrySchema).default([]),
  parameters: z.record(z.string(), z.unknown()).default({}),
  tags: z.array(z.string()).default([]),
});

export const aiPromptEditSchema = z.object({
  promptId: z.string().min(1),
  revisionId: z.string().min(1),
  promptBody: z.string().min(1),
});

export const promptSchema = z.object({
  id: z.string(),
  title: z.string(),
  modelName: z.string(),
  owner: z.string(),
  access: z.enum(['private', 'workspace']),
  status: promptStatusSchema,
  revision: z.string(),
  updatedAt: z.string(),
  tags: z.array(z.string()),
  folderId: z.string().optional(),
});

export const promptDetailSchema = promptSchema.extend({
  purpose: z.string(),
  provider: z.string(),
  providerModel: z.string(),
  fallbackAnswer: z.string(),
  promptBody: z.string(),
  revisions: z.array(revisionSchema),
});

export const reviewSchema = z.object({
  id: z.string(),
  promptId: z.string(),
  promptTitle: z.string(),
  revision: z.string(),
  owner: z.string(),
  submittedAt: z.string(),
  summary: z.string(),
  passed: z.number().int().nonnegative(),
  total: z.number().int().positive(),
  candidateCost: z.number().nonnegative(),
  releasedCost: z.number().nonnegative(),
});

export const providerSchema = z.object({
  id: z.string(),
  name: z.string(),
  models: z.array(z.string()),
  state: z.enum(['connected', 'attention']),
  updatedAt: z.string(),
});

// The ceiling every prompt body is held to server-side: `MAX_CANONICAL_CHARACTERS`
// in src/prope/canonical_prompt.py. A revision body, a conversion source and the
// similarity probe are all refused above it, so the upload refuses there too — a
// file somebody watches load and then cannot save is a worse failure than one
// that never loaded.
export const MAX_SOURCE_CHARACTERS = 32_768;

// What `POST /api/v1/prompt-conversions` accepts as `source_format`. `xml` is
// absent on purpose: canonical XML is what conversion PRODUCES, so a source
// already in it has nothing to convert. The editor's own set adds it back below,
// because an uploaded `.xml` file is still a source the import flow must carry.
export const conversionSourceFormatSchema = z.enum(['txt', 'markdown', 'json', 'yaml']);
export const promptSourceFormatSchema = z.enum(['txt', 'markdown', 'json', 'yaml', 'xml']);

// Every surface that edits an EXISTING revision spreads this: there is a body
// already and nothing to import, so the source half of the form is inert and
// `promptBody` is what gets validated. Written once so the three fields cannot
// drift apart across the four screens that build editor values.
export const AUTHORED_SOURCE = { sourceMode: 'authored', sourceText: '', sourceFormat: 'txt' } as const;

export const promptEditorSchema = z
  .object({
    title: z.string().min(2),
    // A-021's `namespace/name`, held as two fields rather than one string.
    //
    // `namespace` is the folder the composer was opened in. It is displayed as a
    // fixed prefix and never typed, which is why the route carries it: a prompt
    // filed in the wrong namespace cannot be moved, only retired and recreated.
    //
    // Both halves are validated against the registry's own `NAME_PATTERN`. The
    // single `modelName` field this replaced used `[a-z0-9-]+` on both halves,
    // which refused the `.` and `_` a folder slug may legally hold — so a folder
    // named `v1.plans` could be created and then never filed into — while
    // admitting a leading `-` that the database itself rejects with a 422.
    namespace: z.string().regex(SLUG_PATTERN),
    name: z.string().regex(SLUG_PATTERN),
    access: z.enum(['private', 'workspace']),
    // The upstream binding, `RevisionCreate`'s `provider_config_id` and
    // `upstream_model`. `''` is unset on both — the pair is optional, and the
    // server holds both columns nullable, so a workspace that has registered no
    // provider yet can still create prompts.
    //
    // These replaced a `provider` select over two hardcoded vendor names and a
    // free-text `providerModel`, neither of which was ever sent: `createRevision`
    // omitted the binding entirely, so every prompt this app created named no
    // provider at all.
    providerConfigId: z.string(),
    upstreamModel: z.string(),
    // Which of the two bindings this revision will carry — ADR-0069. A revision
    // takes a pair or a route, never both, and the server refuses the pair
    // alongside a `router_combo_id` on a database constraint. Held as a mode
    // rather than inferred from which field is filled, so switching back and
    // forth does not destroy the other choice: exclusivity is applied at the
    // SEND site, where the server can trust it.
    //
    // Required, not `.default()`, for the reason spelled out below on the
    // source fields: a default makes zod's input type differ from its output
    // type, and `useForm<PromptEditorValues>` is typed on the output.
    bindingMode: z.enum(['single', 'combo']),
    /** `''` is unset. Meaningful only while `bindingMode` is `combo`. */
    routeComboId: z.string(),
    promptBody: z.string(),
    fallbackAnswer: z.string().min(1),
    changeSummary: z.string().min(4),
    tags: z.array(z.string().trim().min(1).max(32)).max(10),
    // The import half of the new-prompt screen. Required rather than defaulted:
    // `.default()` would make zod's INPUT type differ from its OUTPUT type, and
    // `useForm<PromptEditorValues>` is typed on the output — so every caller of
    // `zodResolver` would need a cast to paper over a mismatch that only exists
    // because these three fields were optional to write down. `AUTHORED_SOURCE`
    // below is the one-line spread that keeps the /edit surfaces unchanged.
    sourceMode: z.enum(['existing', 'authored']),
    sourceText: z.string(),
    sourceFormat: promptSourceFormatSchema,
    sourceFilename: z.string().optional(),
  })
  // Which field carries the prompt depends on which tab is open, so the check
  // cannot live on either field alone. `authored` requires canonical XML in
  // `promptBody`, because that is what the block editor writes. `existing`
  // requires raw text in `sourceText` and deliberately does NOT require XML:
  // converting it is the next step of the flow, not a precondition of it.
  .superRefine((values, context) => {
    // `ck_revision_binding_is_whole`, mirrored. A model with no configuration
    // resolves to whichever provider the next piece of code happens to pick,
    // which is the implicit default that makes a released revision untraceable.
    // Checked here so the pair cannot be half-filled on screen rather than
    // discovered as a 422 after the duplicate check has already run.
    if (values.bindingMode === 'combo') {
      // Asymmetric with the pair below, on purpose. Switching to combo mode is
      // a deliberate act with exactly one thing to fill in, so leaving it empty
      // is a mistake — while an empty PAIR stays legal, because a workspace
      // that has registered no provider yet must still be able to register a
      // prompt.
      if (values.routeComboId === '') {
        context.addIssue({ code: 'custom', path: ['routeComboId'], message: 'required' });
      }
      return;
    }
    if ((values.providerConfigId === '') !== (values.upstreamModel === '')) {
      context.addIssue({ code: 'custom', path: ['upstreamModel'], message: 'incomplete' });
    }
    if (values.sourceMode === 'authored') {
      if (values.promptBody.length < 20 || !parseXmlBlocks(values.promptBody).success) {
        context.addIssue({ code: 'custom', path: ['promptBody'], message: 'malformed' });
      }
      return;
    }
    if (values.sourceText.trim().length < 20) {
      context.addIssue({ code: 'custom', path: ['sourceText'], message: 'tooShort' });
    }
    if (values.sourceText.length > MAX_SOURCE_CHARACTERS) {
      context.addIssue({ code: 'custom', path: ['sourceText'], message: 'tooLong' });
    }
  });

// `POST /api/v1/prompt-conversions` — untrusted source in, canonical XML out.
// The model and schema version travel back so the revision can record WHICH
// converter produced the body it stores (RevisionCreate's provenance fields).
export const promptConversionReadSchema = z.object({
  xml_body: z.string(),
  model: z.string(),
  schema_version: z.string(),
});

<<<<<<< Updated upstream
=======
export type PromptConversionRead = z.infer<typeof promptConversionReadSchema>;

export const providerFormSchema = z.object({
  provider: z.string().min(1),
  credential: z.string().min(8),
  model: z.string().min(1),
});

>>>>>>> Stashed changes
export const releaseFormSchema = z.object({
  action: z.enum(['normal', 'restore', 'breakGlass']),
  targetRevision: z.string().min(1),
  reason: z.string(),
}).superRefine((value, context) => {
  if (value.action === 'breakGlass' && value.reason.trim().length < 4) {
    context.addIssue({ code: 'custom', path: ['reason'], message: 'reasonRequired' });
  }
});

export const workflowStatusSchema = z.enum(['pending', 'running', 'passed', 'warning', 'failed', 'waiting', 'skipped']);
export const workflowStageSchema = z.enum(['prepare', 'engineer', 'evaluation', 'reviewer', 'canary']);
export const workflowStepIdSchema = z.enum([
  'LoadContext', 'RetrieveKnowledge', 'AnalyzePrompt', 'OptimizePrompt', 'WaitEngineerApproval',
  'CreateCandidate', 'RunEval', 'CostAnalysis', 'RegressionGate', 'ExplainResults', 'ExplainFailure',
  'WaitReviewerApproval', 'StartCanary', 'ObserveCanary', 'CanaryGate', 'WaitProductionApproval',
  'Rollback', 'ValidateBaseline', 'PromoteProduction', 'StoreLesson',
]);
export const workflowBranchSchema = z.enum(['approve', 'rejectRevise', 'retry', 'requestChanges', 'extend', 'staleBaseline', 'rollback']);
export const workflowStepSchema = z.object({
  id: workflowStepIdSchema,
  stage: workflowStageSchema,
  status: workflowStatusSchema,
  startedAt: z.string().optional(),
  endedAt: z.string().optional(),
  durationSeconds: z.number().nonnegative().optional(),
  result: z.string().optional(),
  warning: z.string().optional(),
  evidence: z.string().optional(),
  metrics: z.array(z.object({ label: z.string(), value: z.string() })).optional(),
  diff: z.object({ before: z.string(), after: z.string() }).optional(),
  branches: z.array(workflowBranchSchema).default([]),
});
export const evaluationWorkflowSchema = z.object({
  promptId: z.string(),
  currentStepId: workflowStepIdSchema,
  steps: z.array(workflowStepSchema),
});
export const workflowActionSchema = z.object({
  promptId: z.string(),
  stepId: workflowStepIdSchema,
  action: z.enum(['approve', 'rejectRevise', 'retry', 'requestChanges', 'extend', 'rollback']),
  reason: z.string().optional(),
});
export const hitlReasonSchema = z.object({ reason: z.string().trim().min(4) });

export const datasetTypeSchema = z.enum(['golden', 'regression', 'red-team']);

export const testCaseSchema = z.object({
  id: z.string(),
  name: z.string(),
  input: z.string(),
  expectedOutput: z.string(),
  metadata: z.record(z.string(), z.string()).optional(),
});

export const datasetSchema = z.object({
  id: z.string(),
  name: z.string(),
  type: datasetTypeSchema,
  tags: z.array(z.string()).default([]),
  description: z.string(),
  testCaseCount: z.number().int().nonnegative(),
  linkedPromptIds: z.array(z.string()).default([]),
  createdAt: z.string(),
  updatedAt: z.string(),
});

export const datasetDetailSchema = datasetSchema.extend({
  testCases: z.array(testCaseSchema),
});

export type DatasetType = z.infer<typeof datasetTypeSchema>;
export type TestCase = z.infer<typeof testCaseSchema>;
export type Dataset = z.infer<typeof datasetSchema>;
export type DatasetDetail = z.infer<typeof datasetDetailSchema>;

export const promptTestInputSchema = z.object({
  promptId: z.string().min(1),
  promptBody: z.string().min(1),
  inputPrompt: z.string().min(1),
  model: z.string().min(1),
  variables: z.record(z.string(), z.string()),
});

export const promptTestResultSchema = z.object({
  output: z.string(),
  requestCost: z.number().nonnegative(),
  inputCost: z.number().nonnegative(),
  outputCost: z.number().nonnegative(),
  inputTokens: z.number().int().nonnegative(),
  outputTokens: z.number().int().nonnegative(),
});

export const evalFailureSchema = z.object({
  id: z.string(),
  caseName: z.string(),
  reason: z.string(),
});

export const evalRunSchema = z.object({
  id: z.string(),
  promptId: z.string(),
  candidateRevisionId: z.string(),
  baselineRevisionId: z.string().nullable(),
  suiteName: z.string(),
  suiteVersion: z.string(),
  datasetName: z.string(),
  caseCount: z.number().int().positive(),
  metrics: z.object({
    faithfulness: z.number().nonnegative(),
    relevance: z.number().nonnegative(),
    completeness: z.number().nonnegative(),
    format: z.number().nonnegative(),
  }),
  tokensDelta: z.number(),
  costDelta: z.number(),
  latencyDelta: z.number(),
  failures: z.array(evalFailureSchema),
  recommendation: z.enum(['readyForReview', 'needsChanges', 'blocked']),
  createdAt: z.string(),
});

export const evalTestResultSchema = z.object({
  id: z.string(),
  name: z.string(),
  input: z.string(),
  expectedOutput: z.string(),
  output: z.string(),
  passed: z.boolean(),
  variables: z.record(z.string(), z.string()),
});

export const evalDatasetResultSchema = z.object({
  id: z.string(),
  name: z.string(),
  type: datasetTypeSchema,
  description: z.string(),
  lastRunAt: z.string().nullable(),
  metrics: z.object({
    accuracy: z.number().min(0).max(1),
    relevance: z.number().min(0).max(1),
    format: z.number().min(0).max(1),
    safety: z.number().min(0).max(1),
  }),
  tests: z.array(evalTestResultSchema),
});

export const evalWorkspaceSchema = z.object({
  promptId: z.string(),
  datasets: z.array(evalDatasetResultSchema),
});

export const productionHourlyPointSchema = z.object({
  ts: z.string(),
  calls: z.number().int().nonnegative(),
  errorRate: z.number().nonnegative(),
});

export const editorSuggestionSchema = z.object({
  id: z.string(),
  kind: z.enum(['grounding', 'refusal', 'format', 'safety']),
  title: z.string(),
  body: z.string(),
  applyTo: z.enum(['append', 'replace']),
});

export const promoteEnvironmentSchema = z.enum(['development', 'staging', 'production']);

// Wizard types for AI Prompt Suggestion
export const wizardStepSchema = z.object({
  id: z.enum(['intent', 'context', 'constraints', 'model']),
  step: z.number().int().nonnegative(),
  questionKey: z.string(),
  options: z.array(z.object({ value: z.string(), labelKey: z.string() })).optional(),
  multiSelect: z.boolean().default(false),
  placeholderKey: z.string().optional(),
});

export const wizardAnswersSchema = z.object({
  intent: z.string(),
  context: z.string(),
  constraints: z.array(z.string()),
  model: z.string(),
  additionalNotes: z.string().optional(),
});

export const promptSuggestionSchema = z.object({
  id: z.string(),
  title: z.string(),
  promptBody: z.string(),
  confidence: z.number().min(0).max(1),
  explanation: z.string(),
  model: z.string(),
});

// Overview Tab type — the four-tab prompt surface:
// Content / Evaluation / Log & Trace / Monitor & Improve.
// `improvement` is an alias of `monitoring` carrying the findings focus anchor.
export const overviewTabSchema = z.enum(['content', 'evaluation', 'logs', 'monitoring', 'improvement']);

export type PromptDetailTab = z.infer<typeof overviewTabSchema>;

/** Legacy tab slugs still circulating in bookmarks and notifications. */
const LEGACY_TAB_MAP: Record<string, PromptDetailTab> = {
  overview: 'content',
  release: 'monitoring',
  production: 'logs',
};

export function normalizeOverviewTab(value: string | null | undefined): PromptDetailTab {
  if (value === null || value === undefined) return 'content';
  return overviewTabSchema.safeParse(value).success ? (value as PromptDetailTab) : LEGACY_TAB_MAP[value] ?? 'content';
}

export interface PlaygroundComparisonParams {
  promptId: string;
  revisionIdA: string;
  revisionIdB: string;
  text: string;
}

export interface PromptDiff {
  before: string;
  after: string;
}

export type Prompt = z.infer<typeof promptSchema>;
export type Revision = z.infer<typeof revisionSchema>;

/**
 * Can this revision reach a model at all? — ADR-0069.
 *
 * One predicate, in one place, because six screens ask it and five of them were
 * asking it about the wrong thing. The rule the database keeps is that a
 * revision binds **a pair or a route, never both**, so a check that only looks
 * at the pair reads a routed revision as unbound — and two of the screens that
 * did turned that into a hard block on a revision that runs perfectly well.
 *
 * `revision.route` is the frozen snapshot, not a reference: it is what the
 * gateway will actually walk, whatever the template in Settings says now.
 */
export function revisionIsBound(revision: Pick<Revision, 'providerConfigId' | 'upstreamModel' | 'route'> | undefined): boolean {
  if (!revision) return false;
  if (revision.route.length > 0) return true;
  return Boolean(revision.providerConfigId && revision.upstreamModel);
}

/**
 * The ONE binding a measurement uses — rung 1 of a route, or the pair.
 *
 * Never a failover. An eval run, a readiness probe and a playground turn all
 * take the primary entry deterministically (A-164): a probe wants the truth
 * about what this binding does, and a cost delta computed against whichever
 * provider happened to be up is not comparable across runs. This mirrors
 * `RevisionRead.primary` on the server, and the two must not drift.
 */
export function revisionPrimaryBinding(
  revision: Pick<Revision, 'providerConfigId' | 'upstreamModel' | 'route'> | undefined,
): { providerConfigId: string; upstreamModel: string } | undefined {
  if (!revision) return undefined;
  const first = revision.route[0];
  if (first) return { providerConfigId: first.provider_config_id, upstreamModel: first.upstream_model };
  if (revision.providerConfigId && revision.upstreamModel) {
    return { providerConfigId: revision.providerConfigId, upstreamModel: revision.upstreamModel };
  }
  return undefined;
}
export type PromptDetail = z.infer<typeof promptDetailSchema>;
export type AiPromptEdit = z.infer<typeof aiPromptEditSchema>;
export type Review = z.infer<typeof reviewSchema>;
export type Provider = z.infer<typeof providerSchema>;
export type PromptEditorValues = z.infer<typeof promptEditorSchema>;
export type PromptSourceFormat = z.infer<typeof promptSourceFormatSchema>;
export type ConversionSourceFormat = z.infer<typeof conversionSourceFormatSchema>;
export type PromptConversionRead = z.infer<typeof promptConversionReadSchema>;
export type ReleaseFormValues = z.infer<typeof releaseFormSchema>;
export type EvaluationWorkflow = z.infer<typeof evaluationWorkflowSchema>;
export type WorkflowStep = z.infer<typeof workflowStepSchema>;
export type WorkflowStepId = z.infer<typeof workflowStepIdSchema>;
export type WorkflowStatus = z.infer<typeof workflowStatusSchema>;
export type WorkflowAction = z.infer<typeof workflowActionSchema>;
export type HitlReasonValues = z.infer<typeof hitlReasonSchema>;
export type PromptTestInput = z.infer<typeof promptTestInputSchema>;
export type PromptTestResult = z.infer<typeof promptTestResultSchema>;
export type EvalRun = z.infer<typeof evalRunSchema>;
export type EvalTestResult = z.infer<typeof evalTestResultSchema>;
export type EvalDatasetResult = z.infer<typeof evalDatasetResultSchema>;
export type EvalWorkspace = z.infer<typeof evalWorkspaceSchema>;
export type EvalFailure = z.infer<typeof evalFailureSchema>;
export type ProductionHourlyPoint = z.infer<typeof productionHourlyPointSchema>;
export type EditorSuggestion = z.infer<typeof editorSuggestionSchema>;
export type PromoteEnvironment = z.infer<typeof promoteEnvironmentSchema>;

// Wizard types
export type WizardStep = z.infer<typeof wizardStepSchema>;
export type WizardAnswers = z.infer<typeof wizardAnswersSchema>;
export type PromptSuggestion = z.infer<typeof promptSuggestionSchema>;

// SDK and API Management types

// Request Trace

// Overview Tab
export type OverviewTab = z.infer<typeof overviewTabSchema>;

// Workspace Stats
export const workspaceStatsSchema = z.object({
  totalPrompts: z.number().int().nonnegative(),
  qualityPercent: z.number().min(0).max(100),
  totalCost7Days: z.number().nonnegative(),
  totalRequests7Days: z.number().int().nonnegative(),
});

export type WorkspaceStats = z.infer<typeof workspaceStatsSchema>;

// ============ PROMPT SEARCH & INDEXING ============
// Wire shapes for the real `prompt_search` backend module. These validate the
// responses of GET/POST/DELETE /api/v1/prompts/search and .../{id}/index, and
// mirror src/prope/prompt_search/schemas.py. The field names stay snake_case
// because they are the wire contract, not the app model.

export const promptSearchResultSchema = z.object({
  prompt_id: z.string(),
  title: z.string(),
  purpose: z.string(),
  similarity: z.number().nullable().optional(),
  keywords: z.array(z.string()),
  topics: z.array(z.string()),
  entities: z.array(z.string()),
  variations: z.record(z.string(), z.array(z.string())),
  language: z.array(z.string()),
  matched_fields: z.array(z.string()),
  is_indexed: z.boolean(),
  body_preview: z.string().nullable().optional(),
});

export const promptSearchResponseSchema = z.object({
  prompts: z.array(promptSearchResultSchema),
  next_cursor: z.string().nullable().optional(),
  total: z.number().nullable().optional(),
  search_type: z.enum(['quick', 'ai']),
});

/** The comparison funnel's answer, alongside the rows it produced.
 *
 * `prompts` is the unchanged row shape so one schema still validates both
 * search routes; `candidates` is the parallel classification, joined by
 * `prompt_id`. A row on this dialog is an accusation that this prompt might be
 * the one you already have, so a candidate the backend judged `unrelated` is
 * not on the list at all — what was checked is a count (`retrieved`,
 * `adjudicated`), not a list. */
export const comparisonFindingSchema = z.object({
  code: z.string(),
  severity: z.enum(['hard', 'soft', 'info']),
  axis: z.string(),
  params: z.record(z.string(), z.unknown()).default({}),
});

/** What two prompts actually share, per canonical block.
 *
 * `score` is a containment over IDF-weighted terms — how much of the incoming
 * block's distinctive vocabulary the candidate also carries. It is NOT a cosine
 * and must never be rendered as "N% similar"; `shared_terms` is the part a
 * reader can argue with, and is why this travels at all. Blocks arrive ordered
 * by how much the ranking weights them, so `instructions` precedes `system`
 * even when persona scored higher — which, between two prompts from one
 * library, it usually does. */
export const comparisonBlockOverlapSchema = z.object({
  block: z.string(),
  score: z.number().default(0),
  shared_terms: z.array(z.string()).default([]),
});

export const comparisonOverlapSchema = z.object({
  blocks: z.array(comparisonBlockOverlapSchema).default([]),
  /** Every block the pre-filter scored, zeros included — `blocks` above lists
   * only what overlapped. The metric grid needs both: without this it cannot
   * tell "these two share nothing in `output_format`" from "neither prompt has
   * an `output_format`", and it would draw the second as `0%`. */
  compared_blocks: z.array(z.string()).default([]),
  shared_variables: z.array(z.string()).default([]),
  variable_overlap: z.number().default(0),
  /** Denominator of `variable_overlap`. Zero means the incoming prompt takes no
   * variables, which is not the same as sharing none of them. */
  variables_required: z.number().default(0),
  metadata_overlap: z.number().default(0),
});

export const comparisonCandidateSchema = z.object({
  prompt_id: z.string(),
  verdict: z.enum(['same', 'supersedes', 'variant', 'related', 'unrelated']),
  action: z.enum(['use_existing', 'add_revision', 'create_new']),
  findings: z.array(comparisonFindingSchema).default([]),
  similarity: z.number().nullable().optional(),
  structural_score: z.number().default(0),
  /** How much of the incoming prompt's distinctive weight this candidate
   * carries, 0..1. **The one number on this row that may be shown as a
   * percentage** — `structural_score` is an unnormalised sum and `score` on a
   * block is a containment for one block alone. It is also the number the
   * display floor is applied to, so a listed row has always cleared it. It says
   * how much of the text overlaps and never that the two prompts do the same
   * job: that claim is `verdict`. */
  match_score: z.number().default(0),
  adjudicated: z.boolean().default(false),
  reasons: z.array(z.string()).default([]),
  overlap: comparisonOverlapSchema.nullable().optional(),
});

export const similarSearchResponseSchema = promptSearchResponseSchema.extend({
  recommended_action: z.enum(['use_existing', 'add_revision', 'create_new']).default('create_new'),
  recommended_prompt_id: z.string().nullable().optional(),
  retrieved: z.number().default(0),
  adjudicated: z.number().default(0),
  /** The `match_score` a candidate had to clear to be listed, and how many were
   * held back by that alone. `below_floor` is what keeps the threshold visible:
   * a row missing because of a floor and a row nothing found look identical
   * otherwise, and only one of them means "no duplicates". */
  match_floor: z.number().default(0),
  below_floor: z.number().default(0),
  candidates: z.array(comparisonCandidateSchema).default([]),
  coverage: z.array(comparisonFindingSchema).default([]),
});

/** One rung of the funnel, as it happens.
 *
 * `step` and `state` are closed vocabularies from `comparison/trace.py` and
 * `params` carries counts only — never a body, never a shared term. The client
 * owns every sentence, as it does for findings (ADR-0053). */
export const similarityStepSchema = z.object({
  step: z.enum(['retrieval', 'prefilter', 'output_contract', 'contracts', 'adjudication', 'verdict']),
  state: z.enum(['started', 'done', 'skipped', 'failed']),
  params: z.record(z.string(), z.unknown()).default({}),
});

export type ComparisonBlockOverlap = z.infer<typeof comparisonBlockOverlapSchema>;
export type ComparisonOverlap = z.infer<typeof comparisonOverlapSchema>;
export type ComparisonFinding = z.infer<typeof comparisonFindingSchema>;
export type ComparisonCandidate = z.infer<typeof comparisonCandidateSchema>;
export type SimilarSearchResponse = z.infer<typeof similarSearchResponseSchema>;
export type SimilarityStep = z.infer<typeof similarityStepSchema>;
export type SimilarityStepName = SimilarityStep['step'];

export const promptIndexStatusSchema = z.object({
  is_indexed: z.boolean(),
  is_stale: z.boolean().default(false),
  indexed_at: z.string().nullable().optional(),
  indexed_by: z.string().nullable().optional(),
  version_id: z.string().nullable().optional(),
  nearest_neighbor: z
    .object({
      prompt_id: z.string(),
      title: z.string().optional(),
      similarity: z.number().nullable().optional(),
    })
    .nullable()
    .optional(),
});

export const promptIndexPreviewSchema = z.object({
  keywords: z.array(z.string()),
  topics: z.array(z.string()),
  entities: z.array(z.string()),
  variations: z.record(z.string(), z.array(z.string())),
  language: z.array(z.string()),
  duplicate_warning: z
    .object({
      prompt_id: z.string(),
      title: z.string(),
      similarity: z.number(),
    })
    .nullable()
    .optional(),
});

export const promptIndexJobSchema = z.object({
  job_id: z.string(),
  status: z.enum(['pending', 'running', 'completed', 'failed']),
  started_at: z.string().nullable().optional(),
  completed_at: z.string().nullable().optional(),
  error: z.string().nullable().optional(),
});

export type PromptSearchResult = z.infer<typeof promptSearchResultSchema>;
export type PromptSearchResponse = z.infer<typeof promptSearchResponseSchema>;
export type PromptIndexStatus = z.infer<typeof promptIndexStatusSchema>;
export type PromptIndexPreview = z.infer<typeof promptIndexPreviewSchema>;
export type PromptIndexJob = z.infer<typeof promptIndexJobSchema>;

// ============ PROMPT REGISTRY (real backend) ============
// Wire shapes for the real `prompt_registry` module — the responses of
// GET /api/v1/prompts, GET /api/v1/prompts/{id}, and the revision endpoints.
// They mirror src/prope/prompt_registry/schemas.py (PromptRead,
// RevisionSummaryRead, RevisionRead) and stay snake_case because they are the
// wire contract; api.ts maps them onto the camelCase app models above.

export const promptReadSchema = z.object({
  prompt_id: z.string(),
  model_name: z.string(),
  namespace: z.string(),
  name: z.string(),
  title: z.string(),
  purpose: z.string(),
  owner_id: z.string(),
  access_level: z.enum(['private', 'workspace']),
  status: z.enum(['active', 'retired']),
  tags: z.array(z.string()),
  released_version_id: z.string().nullable().optional(),
  released_at: z.string().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const revisionSummaryReadSchema = z.object({
  version_id: z.string(),
  prompt_id: z.string(),
  revision_number: z.number().int(),
  change_summary: z.string(),
  author_id: z.string(),
  author_email: z.string().email().nullable().optional(),
  tags: z.array(z.string()).default([]),
  status: z.enum(['Draft', 'In review', 'Approved']),
  provider_config_id: z.string().nullable().optional(),
  upstream_model: z.string().nullable().optional(),
  // The frozen route, inline — ADR-0069. Not a reference to resolve: four
  // screens need the rungs, several of them render inside lists, and this app
  // already fetches each revision's body one call at a time. A per-revision
  // route fetch would turn that existing N+1 into 2N+1.
  //
  // `route_combo_name` is snapshotted beside the id so a review screen still
  // reads correctly after somebody renames the template — or deletes it.
  route_combo_id: z.string().nullable().optional(),
  route_combo_name: z.string().nullable().optional(),
  route: z.array(routerComboEntrySchema).default([]),
  created_at: z.string(),
});

export const revisionReadSchema = revisionSummaryReadSchema.extend({
  body: z.string(),
  parameters: z.record(z.string(), z.unknown()),
  fallback_answer: z.string().nullable().optional(),
  original_body: z.string(),
  original_format: z.string(),
  original_filename: z.string().nullable().optional(),
  conversion_model: z.string().nullable().optional(),
  conversion_schema_version: z.string().nullable().optional(),
});

export type PromptRead = z.infer<typeof promptReadSchema>;
export type RevisionSummaryRead = z.infer<typeof revisionSummaryReadSchema>;
export type RevisionRead = z.infer<typeof revisionReadSchema>;
