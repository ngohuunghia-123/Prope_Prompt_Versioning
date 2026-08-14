import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { AIPromptWizard } from '@/features/prompt-lifecycle/components/AIPromptWizard';
import type { PromptSuggestion } from '@/features/prompt-lifecycle/types';

export function PromptWizardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const handleComplete = (suggestion: PromptSuggestion) => {
    navigate('/app/prompts/new', { state: { suggestion } });
  };

  const handleCancel = () => {
    navigate('/app/prompts');
  };

  return (
    <div className="container mx-auto max-w-4xl px-4 py-8">
      <div className="mb-8 text-center">
        <h1 className="font-display text-display-1 text-ink">{t('lifecycle.wizard.pageTitle')}</h1>
        <p className="mt-2 text-body text-muted">{t('lifecycle.wizard.pageDescription')}</p>
      </div>
      <AIPromptWizard onComplete={handleComplete} onCancel={handleCancel} />
    </div>
  );
}
