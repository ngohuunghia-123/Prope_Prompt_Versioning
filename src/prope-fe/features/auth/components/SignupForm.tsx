import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowRight } from '@phosphor-icons/react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { z } from 'zod';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useSignupMutation } from '@/features/auth/queries';
import { getReturnTo } from '@/features/auth/returnTo';
import { isApiError } from '@/lib/apiClient';

const signupSchema = z.object({
  displayName: z.string().trim().min(2),
  email: z.email(),
  password: z.string().min(8),
  confirmPassword: z.string().min(8),
}).refine((values) => values.password === values.confirmPassword, { path: ['confirmPassword'] });

type SignupValues = z.infer<typeof signupSchema>;

export function SignupForm() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const signupMutation = useSignupMutation();
  const { register, handleSubmit, formState: { errors } } = useForm<SignupValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: { displayName: '', email: '', password: '', confirmPassword: '' },
  });
  const onSubmit = handleSubmit(async (values) => {
    try {
      await signupMutation.mutateAsync({ displayName: values.displayName, email: values.email, password: values.password });
      void navigate(getReturnTo(location.search), { replace: true });
    } catch {
      // Mutation state owns the visible API error.
    }
  });

  return (
    <form className="space-y-5" onSubmit={(event) => void onSubmit(event)} noValidate>
      <Input label={t('auth.signup.displayName')} autoComplete="name" autoFocus disabled={signupMutation.isPending} error={errors.displayName ? t('auth.signup.displayNameError') : undefined} {...register('displayName')} />
      <Input label={t('auth.email')} type="email" autoComplete="email" disabled={signupMutation.isPending} error={errors.email ? t('auth.emailError') : undefined} {...register('email')} />
      <Input label={t('auth.signup.password')} type="password" autoComplete="new-password" disabled={signupMutation.isPending} error={errors.password ? t('auth.passwordError') : undefined} {...register('password')} />
      <Input label={t('auth.signup.confirmPassword')} type="password" autoComplete="new-password" disabled={signupMutation.isPending} error={errors.confirmPassword ? t('auth.signup.confirmPasswordError') : undefined} {...register('confirmPassword')} />
      {signupMutation.isError ? <div role="alert" className="rounded-lg bg-danger p-3 text-body text-danger-text">{isApiError(signupMutation.error) && signupMutation.error.status === 409 ? t('auth.signup.emailExists') : t('auth.systemError')}</div> : null}
      <Button className="w-full justify-center" type="submit" loading={signupMutation.isPending} trailingIcon={<ArrowRight aria-hidden className="size-4" />}>{t('auth.signup.submit')}</Button>
    </form>
  );
}
