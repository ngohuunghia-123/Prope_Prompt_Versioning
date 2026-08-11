import { zodResolver } from '@hookform/resolvers/zod';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState, type FormEvent } from 'react';
import { useForm } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import { useCreatePrompt } from '@/features/preservation/queries';
import { modelNameAvailabilityOptions, registrationMetadataOptions } from '@/features/registration/queries';
import { registrationFormSchema, type RegistrationFormValues } from '@/features/registration/types';

export function useRegisterPromptFlow() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [step, setStep] = useState(0);
  const [canRegister, setCanRegister] = useState(false);
  const metadata = useQuery(registrationMetadataOptions);
  const registerPrompt = useCreatePrompt();
  const form = useForm<RegistrationFormValues>({
    resolver: zodResolver(registrationFormSchema), mode: 'onBlur',
    defaultValues: { source: 'manual', title: '', purpose: '', content: '', tags: '', modelName: '', providerName: 'OpenAI Primary', upstreamModel: 'gpt-5.2', temperature: 0.2, maxTokens: 1200, fallbackAnswer: '', ownerId: 'linh', ownerName: 'Linh Nguyễn', access: 'private' },
  });

  useEffect(() => {
    if (step !== 2) {
      setCanRegister(false);
      return;
    }
    const timer = window.setTimeout(() => setCanRegister(true), 500);
    return () => window.clearTimeout(timer);
  }, [step]);

  const next = async () => {
    if (step === 0 && await form.trigger(['title', 'modelName', 'purpose', 'content'])) {
      const availability = await queryClient.fetchQuery(modelNameAvailabilityOptions(form.getValues('modelName')));
      if (!availability.available) { form.setError('modelName', { message: 'modelNameUnavailable' }); return; }
      form.clearErrors('modelName');
      setStep(1);
    }
    if (step === 1 && await form.trigger(['providerName', 'upstreamModel', 'temperature', 'maxTokens'])) setStep(2);
  };
  const back = () => setStep((current) => Math.max(0, current - 1));
  const selectProvider = (providerName: string) => {
    const provider = metadata.data?.providers.find((candidate) => candidate.name === providerName);
    form.setValue('providerName', providerName);
    form.setValue('upstreamModel', provider?.models[0] ?? '');
  };
  const selectOwner = (ownerId: string) => {
    const owner = metadata.data?.owners.find((candidate) => candidate.id === ownerId);
    form.setValue('ownerId', ownerId); form.setValue('ownerName', owner?.name ?? '');
  };
  const register = form.handleSubmit(async (values) => {
    const prompt = await registerPrompt.mutateAsync(values);
    navigate(`/app/prompts/${prompt.id}`, { replace: true });
  });
  const submit = (event: FormEvent<HTMLFormElement>) => {
    if (step < 2) {
      event.preventDefault();
      void next();
      return;
    }
    if (!canRegister) {
      event.preventDefault();
      return;
    }
    void register(event);
  };

  return { form, step, canRegister, metadata, registerPrompt, next, back, selectProvider, selectOwner, submit };
}
