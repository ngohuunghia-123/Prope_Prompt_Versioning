import { useQuery } from '@tanstack/react-query';
import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { sessionOptions } from '@/features/auth/queries';
import { foldersOptions } from '@/features/prompt-lifecycle/queries';
import { workspaceMembersOptions } from '@/features/workspace/memberQueries';

const INTERNAL_ID = /^(?:usr|mem|wsp|fld|prm|rev)_[A-Za-z0-9]+$/;

export function useWorkspaceDisplayNames() {
  const { t } = useTranslation();
  const session = useQuery(sessionOptions);
  const workspaceId = session.data?.user.workspaceId ?? '';
  const members = useQuery({
    ...workspaceMembersOptions(workspaceId, 'all'),
    enabled: workspaceId !== '',
  });
  const folders = useQuery(foldersOptions);

  const userName = useCallback((identity: string) => {
    if (identity === session.data?.user.id) return session.data.user.displayName;
    const member = members.data?.items.find((item) => item.userId === identity);
    if (member?.displayName) return member.displayName;
    return INTERNAL_ID.test(identity) ? t('lifecycle.identity.unknownMember') : identity;
  }, [members.data?.items, session.data?.user, t]);

  const folderName = useCallback((folderId?: string) => {
    if (!folderId) return t('lifecycle.identity.unknownFolder');
    return folders.data?.find((folder) => folder.id === folderId)?.name
      ?? t('lifecycle.identity.unknownFolder');
  }, [folders.data, t]);

  return { folderName, userName };
}
