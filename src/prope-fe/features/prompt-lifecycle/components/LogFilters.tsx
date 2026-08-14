import { MagnifyingGlass } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';

interface LogFiltersProps {
  search: string;
  technology: string;
  type: string;
  onSearchChange: (value: string) => void;
  onTechnologyChange: (value: string) => void;
  onTypeChange: (value: string) => void;
}

export function LogFilters({ search, technology, type, onSearchChange, onTechnologyChange, onTypeChange }: LogFiltersProps) {
  const { t } = useTranslation();
  return (
    <div className="grid gap-3 border-b border-border bg-subtle/40 p-4 md:grid-cols-4">
      <div className="md:col-span-2">
        <Input
          label={t('lifecycle.overview.logs.searchLabel')}
          labelHidden
          type="search"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder={t('lifecycle.overview.logs.searchPlaceholder')}
          leadingIcon={<MagnifyingGlass className="size-4" />}
        />
      </div>
      <Select
        label={t('lifecycle.overview.logs.technology')}
        labelHidden
        value={technology}
        onValueChange={onTechnologyChange}
        options={['all', 'OpenAI', 'Claude', 'Gemini'].map((value) => ({ value, label: value === 'all' ? t('lifecycle.overview.logs.allTechnologies') : value }))}
      />
      <Select
        label={t('lifecycle.overview.logs.type')}
        labelHidden
        value={type}
        onValueChange={onTypeChange}
        options={['all', 'system', 'custom', 'agent'].map((value) => ({ value, label: value === 'all' ? t('lifecycle.overview.logs.allTypes') : t(`lifecycle.overview.logs.types.${value}`) }))}
      />
    </div>
  );
}
