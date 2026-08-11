import { SignIn, UserPlus } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { SegmentedControl, type SegmentOption } from '@/components';

export interface AuthModeSwitchProps { value: 'signup' | 'login'; }

export function AuthModeSwitch({ value }: AuthModeSwitchProps) {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const options: SegmentOption[] = [
    {
      value: 'signup',
      label: t('auth.mode.signup'),
      icon: <UserPlus className="size-4" />,
    },
    {
      value: 'login',
      label: t('auth.mode.login'),
      icon: <SignIn className="size-4" />,
    },
  ];

  return (
    <SegmentedControl
      className="max-w-none"
      label={t('auth.mode.label')}
      name="auth-mode"
      options={options}
      value={value}
      onValueChange={(nextValue) => void navigate({ pathname: nextValue === 'signup' ? '/signup' : '/login', search: location.search })}
    />
  );
}
