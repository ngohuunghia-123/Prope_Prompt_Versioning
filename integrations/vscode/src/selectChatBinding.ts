import * as vscode from 'vscode';
import { z } from 'zod';
import { sessionBindingSchema } from '@connector/sessionChatContracts';
import { ConnectorError, type ManagementApi } from './api';

const t = vscode.l10n.t;
export async function selectChatBinding(api: ManagementApi) {
  const providers = z.array(z.object({ provider_config_id: sessionBindingSchema.shape.provider_config_id, display_name: z.string().max(200) })).parse(await api.request('/api/v1/providers'));
  if (!providers.length) throw new ConnectorError('provider_required');
  const provider = await vscode.window.showQuickPick(providers.map((item) => ({
    label: item.display_name.replace(/[$\p{Cc}\p{Cf}]/gu, ''), description: item.provider_config_id, id: item.provider_config_id,
  })), { placeHolder: t('Choose the provider binding for this prompt revision (no credentials are shared)') });
  if (!provider) return null;
  const models = z.array(z.object({ model_id: z.string().min(1).max(200).refine((value) => !/[\p{Cc}\p{Cf}]/u.test(value)), available: z.boolean() })).parse(await api.request(`/api/v1/providers/${encodeURIComponent(provider.id)}/models`));
  const available = models.filter((model) => model.available);
  if (!available.length) throw new ConnectorError('model_required');
  const model = await vscode.window.showQuickPick(available.map((item) => ({ label: item.model_id.replaceAll('$', ''), id: item.model_id })), { placeHolder: t('Choose the model binding for this prompt revision') });
  return model ? { provider_config_id: provider.id, upstream_model: model.id } : null;
}
