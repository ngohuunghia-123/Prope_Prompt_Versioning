import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowRight } from '@phosphor-icons/react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { z } from 'zod';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useLoginMutation } from '@/features/auth/queries';
import { getChangePasswordPath, getReturnTo } from '@/features/auth/returnTo';
import { isApiError } from '@/lib/apiClient';

const loginSchema = z.object({
  email: z.email(),
  password: z.string().min(8),
});

type LoginValues = z.infer<typeof loginSchema>;

export function LoginForm() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const loginMutation = useLoginMutation();
  const { register, handleSubmit, formState: { errors } } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  });
  const onSubmit = handleSubmit(async (values) => {
    try {
      const session = await loginMutation.mutateAsync(values);
      const returnTo = getReturnTo(location.search);
      void navigate(session.mustChangePassword ? getChangePasswordPath(returnTo) : returnTo, { replace: true });
    } catch {
      // The mutation state renders the same response for every failed credential check.
    }
  });
  return (
    <form className="space-y-5" onSubmit={(event) => void onSubmit(event)} noValidate>
      <Input
        label={t('auth.email')}
        type="email"
        autoComplete="email"
        autoFocus
        disabled={loginMutation.isPending}
        error={errors.email ? t('auth.emailError') : undefined}
        {...register('email')}
      />
      <Input
        label={t('auth.password')}
        type="password"
        autoComplete="current-password"
        disabled={loginMutation.isPending}
        error={errors.password ? t('auth.passwordError') : undefined}
        {...register('password')}
      />
      {loginMutation.isError ? (
        <div role="alert" className="rounded-lg bg-danger p-3 text-body text-danger-text">
          <p>{isApiError(loginMutation.error) && loginMutation.error.status === 401 ? t('auth.invalid') : t('auth.systemError')}</p>
          {!isApiError(loginMutation.error) || loginMutation.error.status !== 401 ? (
            <button type="button" className="mt-2 font-semibold underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-focus" onClick={() => void onSubmit()}>{t('common.tryAgain')}</button>
          ) : null}
        </div>
      ) : null}
      <Button
        className="w-full justify-center"
        type="submit"
        loading={loginMutation.isPending}
        trailingIcon={<ArrowRight aria-hidden className="size-4" />}
      >
        {t('auth.submit')}
      </Button>
    </form>
  );
}
