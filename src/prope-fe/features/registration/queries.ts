import { queryOptions } from '@tanstack/react-query';
import { readMockPromptsSnapshot } from '@/features/preservation/queries';
import { registrationMetadataSchema } from '@/features/registration/types';

const wait = () => new Promise((resolve) => window.setTimeout(resolve, 420));

export const registrationMetadataOptions = queryOptions({
  queryKey: ['registration-metadata'],
  queryFn: async () => {
    await wait();
    return registrationMetadataSchema.parse({
      owners: [
        { id: 'linh', name: 'Linh Nguyễn', role: 'owner' },
        { id: 'an', name: 'An Trần', role: 'product' },
        { id: 'mai', name: 'Mai Lê', role: 'engineer' },
      ],
      providers: [
        { id: 'openai-primary', name: 'OpenAI Primary', models: ['gpt-5.2', 'gpt-5.2-mini'] },
        { id: 'azure-openai', name: 'Azure OpenAI', models: ['gpt-5.1', 'gpt-4.1'] },
      ],
    });
  },
});

export const modelNameAvailabilityOptions = (modelName: string) => queryOptions({
  queryKey: ['model-name-availability', modelName.toLocaleLowerCase()],
  queryFn: async () => {
    await wait();
    const normalized = modelName.trim().toLocaleLowerCase();
    return { available: !readMockPromptsSnapshot().some((prompt) => prompt.modelName.toLocaleLowerCase() === normalized) };
  },
  staleTime: 0,
});
