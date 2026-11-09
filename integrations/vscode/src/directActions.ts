import { z } from 'zod';
import { randomUUID } from 'node:crypto';
import { attachmentWriteSchema, datasetWriteSchema, directCaptureSchema, directRevisionSchema, improvementReviewSchema, improvementTargetSchema, PANEL_OWNER, revisionTargetSchema } from '@connector/directContracts';
import { ConnectorError, type ManagementApi } from './api';
import { fingerprint, type Proposals } from './proposals';
import { evaluationProposalSchema } from '@connector/contracts';

const evidenceSchema = z.object({ prompt_id: z.string(), version_id: z.string(), status: z.string() });
const agentSchema = z.object({ run_id: z.string(), kind: z.string(), prompt_id: z.string().nullable(), version_id: z.string().nullable(), status: z.string(), result_actions: z.array(z.record(z.string(), z.string())) });

export class DirectActions {
  private generation = 0;
  private readonly busy = new Set<string>();
  constructor(private readonly api: ManagementApi, private readonly proposals: Proposals,
    private readonly confirm: (operation: 'run' | 'improve') => Promise<boolean>) {}
  clear() { this.generation += 1; }
  private current(generation: number) { if (generation !== this.generation) throw new ConnectorError('session_changed'); }
  private async write(generation: number, path: string, method: 'POST' | 'PUT', body: unknown) {
    this.current(generation);
    const result = await this.api.request(path, method, body);
    this.current(generation);
    return result;
  }
  async execute(action: string, payload: unknown): Promise<unknown> {
    const generation = this.generation;
    const session = await this.api.session();
    if (!session.user.workspace_id) throw new ConnectorError('workspace_required', 403);
    if (session.must_change_password) throw new ConnectorError('password_change_required', 403);
    if (action === 'capture_direct') {
      const input = directCaptureSchema.parse(payload);
      const folders = z.array(z.object({ slug: z.string() })).parse(await this.api.request('/api/v1/folders'));
      if (!folders.some((folder) => folder.slug === input.namespace)) throw new ConnectorError('scope_denied', 403);
      this.current(generation);
      return this.proposals.add(PANEL_OWNER, { kind: 'capture', source: input.source, format: input.format, host: 'other' }, input.namespace);
    }
    if (action === 'create_dataset') {
      const input = datasetWriteSchema.parse(payload); this.current(generation);
      return this.write(generation, '/api/v1/datasets', 'POST', input);
    }
    if (action === 'stage_comparison') {
      const input = evaluationProposalSchema.parse(payload); const prompt = await this.api.prompt(input.prompt_id);
      this.current(generation);
      return this.proposals.addEvaluation(PANEL_OWNER, { kind: 'evaluation', ...input }, prompt.namespace);
    }
    if (action === 'stage_revision') {
      const input = directRevisionSchema.parse(payload);
      const prompt = await this.api.prompt(input.prompt_id); const base = await this.api.revision(input.version_id);
      if (base.prompt_id !== input.prompt_id) throw new ConnectorError('invalid_base');
      this.current(generation);
      return this.proposals.add(PANEL_OWNER, { kind: 'revision', prompt_id: input.prompt_id, base_version_id: input.version_id, source: input.source, format: input.format, host: 'other' }, prompt.namespace);
    }
    if (action === 'attach_datasets') {
      const input = attachmentWriteSchema.parse(payload); await this.api.prompt(input.prompt_id); this.current(generation);
      return this.write(generation, `/api/v1/prompts/${encodeURIComponent(input.prompt_id)}/dataset-attachments`, 'PUT', { dataset_ids: input.dataset_ids });
    }
    if (action === 'run_revision' || action === 'start_improvement') {
      const improvement = action === 'start_improvement' ? improvementTargetSchema.parse(payload) : undefined;
      const input = improvement ?? revisionTargetSchema.parse(payload);
      const key = `${action}:${input.prompt_id}:${input.version_id}`;
      if (this.busy.has(key)) throw new ConnectorError('operation_in_progress');
      this.busy.add(key);
      try {
        const revision = await this.api.revision(input.version_id);
        if (revision.prompt_id !== input.prompt_id) throw new ConnectorError('invalid_base');
        const attachmentPath = `/api/v1/prompts/${encodeURIComponent(input.prompt_id)}/dataset-attachments`;
        const attachments = action === 'run_revision' ? await this.api.request(attachmentPath) : null;
        if (action === 'run_revision' && (!Array.isArray(attachments) || attachments.length === 0)) throw new ConnectorError('dataset_required');
        if (improvement) {
          const evidence = evidenceSchema.parse(await this.api.request(`/api/v1/eval-runs/${encodeURIComponent(improvement.eval_run_id)}`));
          if (evidence.prompt_id !== input.prompt_id || evidence.version_id !== input.version_id || evidence.status !== 'completed') throw new ConnectorError('invalid_evidence');
        }
        if (!await this.confirm(action === 'run_revision' ? 'run' : 'improve')) throw new ConnectorError('cancelled');
        if (fingerprint(await this.api.revision(input.version_id)) !== fingerprint(revision)) throw new ConnectorError('base_changed');
        if (action === 'run_revision' && fingerprint(await this.api.request(attachmentPath)) !== fingerprint(attachments)) throw new ConnectorError('configuration_changed');
        this.current(generation);
        if (improvement) return this.write(generation, '/api/v1/agent-runs', 'POST', {
          kind: 'improvement', plan_basis: 'explicit_user_action', ...improvement, evidence_source: 'eval_analysis', idempotency_key: `connector-improvement:${randomUUID()}`,
        });
        return this.write(generation, `/api/v1/prompts/${encodeURIComponent(input.prompt_id)}/eval-runs/from-attachments`, 'POST', { version_id: input.version_id, include_released_baseline: false });
      } finally { this.busy.delete(key); }
    }
    if (action === 'review_improvement') {
      const input = improvementReviewSchema.parse(payload);
      const run = agentSchema.parse(await this.api.request(`/api/v1/agent-runs/${encodeURIComponent(input.run_id)}`));
      if (run.kind !== 'improvement' || run.prompt_id !== input.prompt_id || run.version_id !== input.version_id || !['succeeded', 'warning', 'waiting_for_user'].includes(run.status)) throw new ConnectorError('invalid_evidence');
      const candidate = run.result_actions.find((entry) => entry.kind === 'open_improvement' && entry.drafted === 'true' && entry.candidate_body);
      if (!candidate?.candidate_body || candidate.candidate_body.length > 32768) throw new ConnectorError('candidate_unavailable');
      const prompt = await this.api.prompt(input.prompt_id); const revision = await this.api.revision(input.version_id);
      if (revision.prompt_id !== input.prompt_id) throw new ConnectorError('invalid_base');
      this.current(generation);
      return this.proposals.add(PANEL_OWNER, { kind: 'revision', prompt_id: input.prompt_id, base_version_id: input.version_id, host: 'other', format: 'xml', source: candidate.candidate_body }, prompt.namespace);
    }
    throw new ConnectorError('action_denied', 403);
  }
}
