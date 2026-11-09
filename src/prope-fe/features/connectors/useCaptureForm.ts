import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useForm, useWatch } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { destinationSchema, type Destination, type Pending, type Preview } from '@/features/connectors/contracts';
import { getProviders, preparePreview, savePreview } from '@/features/connectors/api';
import type { RevisionRead } from '@/features/prompt-lifecycle/types';
import { getProviderModels } from '@/features/prompt-lifecycle/providerApi';
import { isCanonicalXml } from '@/features/prompt-lifecycle/xmlBlocks';
import { ApiError } from '@/lib/apiClient';

export function useCaptureForm(proposal: Pending, promptId: string, base?: RevisionRead) {
  const [preview, setPreview] = useState<Preview>();
  const providers = useQuery({ queryKey: ['connector', 'providers'], queryFn: getProviders });
  const form = useForm<Destination>({ resolver: zodResolver(destinationSchema), defaultValues: {
    prompt_id: promptId, namespace: proposal.namespace, name: promptId ? 'existing' : '', title: promptId ? 'existing' : '',
    base_version_id: base?.version_id ?? '', provider_config_id: base?.provider_config_id ?? '',
    upstream_model: base?.upstream_model ?? '', change_summary: '',
  } });
  const values = useWatch({ control: form.control });
  const providerId = values.provider_config_id ?? '';
  const models = useQuery({ queryKey: ['connector', 'models', providerId], queryFn: () => getProviderModels(providerId), enabled: Boolean(providerId) });
  const parsed = destinationSchema.safeParse(values);
  const previewCurrent = Boolean(preview && parsed.success && JSON.stringify(parsed.data) === JSON.stringify(preview.destination));
  const convert = useMutation({ mutationFn: (destination: Destination) => {
    if (proposal.input.kind !== 'evaluation' && proposal.input.format === 'xml' && !isCanonicalXml(proposal.input.source)) throw new ApiError(422, 'invalid_canonical_xml', 'invalid_canonical_xml');
    return preparePreview(proposal.id, destination);
  }, onMutate: () => setPreview(undefined), onSuccess: setPreview });
  const save = useMutation({ mutationFn: () => {
    if (!preview || !previewCurrent) throw new Error('preview_required');
    return savePreview(proposal.id, preview.digest);
  } });
  return { form, providers, models, preview, previewCurrent, convert, save };
}
