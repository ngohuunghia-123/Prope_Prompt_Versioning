import { useTranslation } from 'react-i18next';
import { ShieldCheck } from '@phosphor-icons/react';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Button } from '@/components/ui/Button';

export function WorkspacePanel() {
  const { t } = useTranslation();

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <h3 className="text-caption font-medium text-muted uppercase tracking-wider">
          {t('settings.workspace.info')}
        </h3>
        <div className="space-y-3">
          <Input
            label={t('settings.workspace.name')}
            value="Prope Workspace"
            onChange={() => {}}
          />
          <Input
            label={t('settings.workspace.description')}
            value="Default workspace for prompt governance"
            onChange={() => {}}
          />
        </div>
      </div>

      <div className="space-y-4">
        <h3 className="text-caption font-medium text-muted uppercase tracking-wider">
          {t('settings.workspace.members')}
        </h3>
        <div className="space-y-2">
          <div className="flex items-center justify-between rounded-lg border border-border bg-surface px-3 py-2.5">
            <div className="flex items-center gap-3">
              <div className="flex size-8 items-center justify-center rounded-full bg-navigation-avatar text-overline font-bold">
                LP
              </div>
              <div className="min-w-0">
                <p className="text-body font-medium text-ink">Lan Pham</p>
                <p className="text-caption text-muted">lan.pham@example.com</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <ShieldCheck aria-hidden className="size-4 text-primary" />
              <span className="text-caption text-primary">{t('settings.workspace.admin')}</span>
            </div>
          </div>

          <div className="flex items-center justify-between rounded-lg border border-border bg-surface px-3 py-2.5">
            <div className="flex items-center gap-3">
              <div className="flex size-8 items-center justify-center rounded-full bg-navigation-avatar text-overline font-bold">
                LN
              </div>
              <div className="min-w-0">
                <p className="text-body font-medium text-ink">Linh Nguyen</p>
                <p className="text-caption text-muted">linh.nguyen@example.com</p>
              </div>
            </div>
            <span className="text-caption text-muted">{t('settings.workspace.member')}</span>
          </div>
        </div>
        <Button type="button" intent="neutral" size="default" className="w-full">
          {t('settings.workspace.inviteMember')}
        </Button>
      </div>

      <div className="space-y-4">
        <h3 className="text-caption font-medium text-muted uppercase tracking-wider">
          {t('settings.workspace.defaultAccess')}
        </h3>
        <Select
          label=""
          value="team"
          options={[
            { value: 'private', label: t('settings.workspace.accessPrivate') },
            { value: 'team', label: t('settings.workspace.accessTeam') },
            { value: 'organization', label: t('settings.workspace.accessOrganization') },
          ]}
          onValueChange={() => {}}
          className="w-full"
        />
        <p className="text-caption text-muted">{t('settings.workspace.defaultAccessHint')}</p>
      </div>
    </div>
  );
}
