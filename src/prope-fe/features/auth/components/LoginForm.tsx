import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowRight } from '@phosphor-icons/react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { z } from 'zod';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useLoginMutation } from '@/features/auth/queries';

const loginSchema = z.object({
  email: z.email(),
  password: z.string().min(8),
});

type LoginValues = z.infer<typeof loginSchema>;

export function LoginForm() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const loginMutation = useLoginMutation();
  const { register, handleSubmit, formState: { errors } } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: 'demo@prope.ai', password: 'prope-demo' },
  });
  const onSubmit = handleSubmit(async (values) => {
    try {
      await loginMutation.mutateAsync(values);
      void navigate('/app/prompts', { replace: true });
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
        error={errors.email ? t('auth.emailError') : undefined}
        {...register('email')}
      />
      <Input
        label={t('auth.password')}
        type="password"
        autoComplete="current-password"
        error={errors.password ? t('auth.passwordError') : undefined}
        {...register('password')}
      />
      {loginMutation.isError ? (
        <p role="alert" className="rounded-lg bg-danger p-3 text-body text-danger-text">{t('auth.invalid')}</p>
      ) : null}
      <Button
        className="w-full"
        type="submit"
        loading={loginMutation.isPending}
        trailingIcon={<ArrowRight aria-hidden className="size-4" />}
      >
        {t('auth.submit')}
      </Button>
    </form>
  );
}
