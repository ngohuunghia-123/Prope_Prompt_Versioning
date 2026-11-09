import { createHash, randomUUID } from 'node:crypto';
import type { Pending, Preview, ProposalInput } from '@connector/contracts';
import { destinationSchema, previewSchema } from '@connector/contracts';
import { z } from 'zod';
import { ConnectorError, ManagementApi } from './api';

export const fingerprint = (value: unknown) => createHash('sha256').update(JSON.stringify(value)).digest('hex');

export class Proposals {
  readonly entries = new Map<string, Pending>();
  private readonly previews = new Map<string, Preview>();
  private readonly busy = new Set<string>();
  private readonly evaluationBases = new Map<string, [string, string]>();
  private generation = 0;
  changed: () => void = () => undefined;
  constructor(private readonly api: ManagementApi) {}
  private forget(id: string) { this.entries.delete(id); this.previews.delete(id); this.evaluationBases.delete(id); }
  discard(id: string) { this.forget(id); this.changed(); }
  clear(connectionId?: string) {
    this.generation += 1;
    for (const [id, entry] of this.entries) if (!connectionId || entry.connection_id === connectionId) this.forget(id);
    this.changed();
  }
  add(connectionId: string, input: ProposalInput, namespace: string) {
    this.list();
    if (this.entries.size >= 5) throw new ConnectorError('proposal_limit');
    const proposal: Pending = { id: randomUUID(), connection_id: connectionId, namespace, input, expires_at: Date.now() + 15 * 60_000, status: 'pending' };
    this.entries.set(proposal.id, proposal); this.changed();
    return { proposal_id: proposal.id, status: 'awaiting_confirmation' };
  }
  list() {
    for (const [id, entry] of this.entries) if (entry.expires_at < Date.now()) this.forget(id);
    return [...this.entries.values()];
  }
  get(id: string) {
    this.list(); const entry = this.entries.get(id);
    if (!entry) throw new ConnectorError('proposal_expired');
    return entry;
  }
  async addEvaluation(connectionId: string, input: Extract<ProposalInput, { kind: 'evaluation' }>, namespace: string) {
    const generation = this.generation;
    const original = await this.api.revision(input.original_version_id);
    const candidate = await this.api.revision(input.candidate_version_id);
    if (original.prompt_id !== input.prompt_id || candidate.prompt_id !== input.prompt_id || original.version_id === candidate.version_id) throw new ConnectorError('invalid_base');
    if (generation !== this.generation) throw new ConnectorError('session_changed');
    const added = this.add(connectionId, input, namespace);
    this.evaluationBases.set(added.proposal_id, [fingerprint(original), fingerprint(candidate)]);
    return added;
  }
  async evaluate(id: string, confirm: () => Promise<boolean>) {
    if (this.busy.has(id)) throw new ConnectorError('operation_in_progress');
    this.busy.add(id);
    try {
      const entry = this.get(id); const input = entry.input; const bases = this.evaluationBases.get(id);
      if (input.kind !== 'evaluation' || entry.status !== 'pending' || !bases) throw new ConnectorError('invalid_proposal');
      const verify = async () => {
        const original = await this.api.revision(input.original_version_id); const candidate = await this.api.revision(input.candidate_version_id);
        if (fingerprint(original) !== bases[0] || fingerprint(candidate) !== bases[1]) throw new ConnectorError('base_changed');
        return { original_body_sha256: createHash('sha256').update(original.body).digest('hex'), candidate_body_sha256: createHash('sha256').update(candidate.body).digest('hex') };
      };
      await verify();
      if (!await confirm()) throw new ConnectorError('cancelled');
      const hashes = await verify(); this.get(id);
      try {
        const result = await this.api.request(`/api/v1/prompts/${encodeURIComponent(input.prompt_id)}/eval-comparisons`, 'POST', {
          original_version_id: input.original_version_id, candidate_version_id: input.candidate_version_id, dataset_id: input.dataset_id, ...hashes,
        });
        entry.status = 'saved'; entry.result = result; this.changed(); return result;
      } catch (error) { entry.status = 'uncertain'; this.changed(); throw error; }
    } finally { this.busy.delete(id); }
  }
  async preview(id: string, rawDestination: unknown) {
    const entry = this.get(id); const destination = destinationSchema.parse(rawDestination);
    if (entry.status !== 'pending' || entry.input.kind === 'evaluation') throw new ConnectorError('invalid_proposal');
    let baseBody = '';
    let baseFingerprint = '';
    if (entry.input.kind === 'revision' && (destination.prompt_id !== entry.input.prompt_id || destination.base_version_id !== entry.input.base_version_id)) throw new ConnectorError('proposal_target_changed');
    if (destination.prompt_id) {
      const prompt = await this.api.prompt(destination.prompt_id);
      if (prompt.namespace !== destination.namespace) throw new ConnectorError('invalid_base');
      if (destination.base_version_id) {
        const base = await this.api.revision(destination.base_version_id);
        if (base.prompt_id !== destination.prompt_id) throw new ConnectorError('invalid_base');
        if (base.route_combo_id || base.provider_config_id !== destination.provider_config_id || base.upstream_model !== destination.upstream_model) throw new ConnectorError('configuration_mismatch');
        baseBody = base.body; baseFingerprint = fingerprint(base);
      } else {
        const revisions = z.array(z.unknown()).parse(await this.api.request(`/api/v1/prompts/${encodeURIComponent(destination.prompt_id)}/revisions`));
        if (revisions.length) throw new ConnectorError('base_required');
      }
    }
    this.get(id);
    const conversion = entry.input.format === 'xml' ? { xml_body: entry.input.source, model: null, schema_version: null }
      : z.object({ xml_body: z.string(), model: z.string(), schema_version: z.string() }).parse(await this.api.request('/api/v1/prompt-conversions', 'POST', {
      source_text: entry.input.source, source_format: entry.input.format,
      ...(destination.prompt_id ? { prompt_id: destination.prompt_id } : {}),
    }));
    const preview: Preview = previewSchema.parse({ proposal_id: id, destination, body: conversion.xml_body, original: entry.input.source, base_body: baseBody, base_fingerprint: baseFingerprint,
      digest: createHash('sha256').update(JSON.stringify({ destination, body: conversion.xml_body, baseBody })).digest('hex'), model: conversion.model, schema_version: conversion.schema_version });
    this.get(id); this.previews.set(id, preview); return preview;
  }
  async save(id: string, digest: string) {
    if (this.busy.has(id)) throw new ConnectorError('operation_in_progress');
    this.busy.add(id);
    try { return await this.saveOnce(id, digest); } finally { this.busy.delete(id); }
  }
  private async saveOnce(id: string, digest: string) {
    const entry = this.get(id); const preview = this.previews.get(id);
    if (!preview || preview.digest !== digest || entry.status !== 'pending' || entry.input.kind === 'evaluation') throw new ConnectorError('preview_required');
    const destination = preview.destination;
    let parameters: Record<string, unknown> = {};
    let fallback: string | null | undefined;
    if (destination.prompt_id && destination.base_version_id) {
      const base = await this.api.revision(destination.base_version_id);
      if (fingerprint(base) !== preview.base_fingerprint) throw new ConnectorError('base_changed');
      parameters = base.parameters;
      fallback = base.fallback_answer;
    }
    try {
      let promptId = destination.prompt_id;
      this.get(id);
      if (!promptId) {
        const created = z.object({ prompt_id: z.string() }).parse(await this.api.request('/api/v1/prompts', 'POST', {
          namespace: destination.namespace, name: destination.name, title: destination.title, access_level: 'private',
        }));
        promptId = created.prompt_id;
        // Keep the exact created target if the subsequent revision write fails.
        preview.destination.prompt_id = promptId;
      }
      this.get(id);
      const result = await this.api.request(`/api/v1/prompts/${encodeURIComponent(promptId)}/revisions`, 'POST', {
        body: preview.body, original_body: preview.original, original_format: entry.input.format,
        provider_config_id: destination.provider_config_id, upstream_model: destination.upstream_model,
        parameters, fallback_answer: fallback ?? null, change_summary: destination.change_summary,
        conversion_model: preview.model, conversion_schema_version: preview.schema_version,
      });
      entry.status = 'saved'; entry.result = result; this.changed(); return result;
    } catch (error) {
      entry.status = 'uncertain'; this.changed();
      // Reconcile by reading; never replay a write whose response was lost.
      if (preview.destination.prompt_id) entry.result = { prompt_id: preview.destination.prompt_id, revisions: await this.api.request(`/api/v1/prompts/${encodeURIComponent(preview.destination.prompt_id)}/revisions`).catch(() => null) };
      throw error;
    }
  }
}
