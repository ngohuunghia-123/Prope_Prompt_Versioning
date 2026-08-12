import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowRight } from '@phosphor-icons/react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { z } from 'zod';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useChangePasswordMutation } from '@/features/auth/queries';
import { getReturnTo } from '@/features/auth/returnTo';
import { isApiError } from '@/lib/apiClient';

const changePasswordSchema = z.object({
  currentPassword: z.string().min(8),
  newPassword: z.string().min(8),
  confirmPassword: z.string().min(8),
})
  .refine((values) => values.newPassword !== values.currentPassword, { path: ['newPassword'] })
  .refine((values) => values.newPassword === values.confirmPassword, { path: ['confirmPassword'] });

type ChangePasswordValues = z.infer<typeof changePasswordSchema>;

export function ChangePasswordForm() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const changePassword = useChangePasswordMutation();
  const { register, handleSubmit, formState: { errors } } = useForm<ChangePasswordValues>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: { currentPassword: '', newPassword: '', confirmPassword: '' },
  });
  const onSubmit = handleSubmit(async ({ currentPassword, newPassword }) => {
    try {
      await changePassword.mutateAsync({ currentPassword, newPassword });
      void navigate(getReturnTo(location.search), { replace: true });
    } catch {
      // The mutation state renders a safe, localized error.
    }
  });
  const currentPasswordInvalid = isApiError(changePassword.error) && changePassword.error.code === 'INVALID_CURRENT_PASSWORD';

  return (
    <form className="space-y-5" onSubmit={(event) => void onSubmit(event)} noValidate>
      <Input label={t('auth.changePassword.current')} type="password" autoComplete="current-password" autoFocus disabled={changePassword.isPending} error={errors.currentPassword || currentPasswordInvalid ? t('auth.changePassword.currentError') : undefined} {...register('currentPassword')} />
      <Input label={t('auth.changePassword.next')} type="password" autoComplete="new-password" disabled={changePassword.isPending} hint={t('auth.changePassword.hint')} error={errors.newPassword ? t('auth.changePassword.passwordError') : undefined} {...register('newPassword')} />
      <Input label={t('auth.changePassword.confirm')} type="password" autoComplete="new-password" disabled={changePassword.isPending} error={errors.confirmPassword ? t('auth.changePassword.confirmError') : undefined} {...register('confirmPassword')} />
      {changePassword.isError && !currentPasswordInvalid ? <p role="alert" className="rounded-lg bg-danger p-3 text-body text-danger-text">{t('auth.systemError')}</p> : null}
      <Button className="w-full" type="submit" loading={changePassword.isPending} trailingIcon={<ArrowRight aria-hidden className="size-4" />}>{t('auth.changePassword.submit')}</Button>
    </form>
  );
}
