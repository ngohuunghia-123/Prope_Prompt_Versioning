import { zodResolver } from '@hookform/resolvers/zod';
import { FloppyDisk } from '@phosphor-icons/react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { profileUpdateSchema, type ProfileUpdateInput } from '@/features/account/profileApi';
import { useUpdateProfileMutation } from '@/features/account/queries';

export interface ProfileFormProps {
  displayName: string;
  email: string;
}

export function ProfileForm({ displayName, email }: ProfileFormProps) {
  const { t } = useTranslation();
  const updateProfile = useUpdateProfileMutation();
  const { register, handleSubmit, formState: { errors, isDirty }, reset } = useForm<ProfileUpdateInput>({
    resolver: zodResolver(profileUpdateSchema),
    defaultValues: { displayName, email },
  });
  const onSubmit = handleSubmit(async (values) => {
    try {
      const saved = await updateProfile.mutateAsync(values);
      reset(saved);
    } catch {
      // Mutation state owns the visible error.
    }
  });

  return (
    <form className="grid gap-5" onSubmit={(event) => void onSubmit(event)} noValidate>
      <Input
        label={t('account.profile.displayName')}
        autoComplete="name"
        disabled={updateProfile.isPending}
        error={errors.displayName ? t('account.profile.displayNameError') : undefined}
        {...register('displayName')}
      />
      <Input
        label={t('account.profile.email')}
        type="email"
        autoComplete="email"
        disabled={updateProfile.isPending}
        error={errors.email ? t('account.profile.emailError') : undefined}
        {...register('email')}
      />
      {updateProfile.isSuccess ? <p role="status" className="text-body text-success-text">{t('account.profile.saved')}</p> : null}
      {updateProfile.isError ? <p role="alert" className="text-body text-danger-text">{t('account.profile.saveError')}</p> : null}
      <div>
        <Button type="submit" disabled={!isDirty} loading={updateProfile.isPending} leadingIcon={<FloppyDisk aria-hidden className="size-4" />}>
          {t('account.profile.save')}
        </Button>
      </div>
    </form>
  );
}
