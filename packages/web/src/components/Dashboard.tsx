import { useEffect, useRef, useState } from 'react';
import { AppShell } from '@astryxdesign/core/AppShell';
import { Layout, LayoutHeader, LayoutContent } from '@astryxdesign/core/Layout';
import { Heading } from '@astryxdesign/core/Heading';
import { Text } from '@astryxdesign/core/Text';
import { Button } from '@astryxdesign/core/Button';
import { Banner } from '@astryxdesign/core/Banner';
import { VStack } from '@astryxdesign/core/VStack';
import { HStack } from '@astryxdesign/core/HStack';
import { useSession } from '../auth/SessionContext';
import UploadQueue from './UploadQueue';
import FileList from './FileList';
import CollectionSidebar, { type View } from './CollectionSidebar';
import TagSearch from './TagSearch';
import ChangeVaultPassword from './ChangeVaultPassword';
import WelcomeCard from './WelcomeCard';
import Wordmark from './brand/Wordmark';
import VaultSwitcher from './VaultSwitcher';
import UnlockVaultDialog from './UnlockVaultDialog';
import NewVaultDialog from './NewVaultDialog';
import ManageVaultsDialog from './ManageVaultsDialog';
import type { VaultEntry } from '../vault/registry';

function viewTitle(view: View): string {
  if (view.kind === 'collection') return view.name;
  if (view.kind === 'tag') return `Tag: ${view.label}`;
  return 'All files';
}

export default function Dashboard() {
  const { logout, rotationInterrupted, activeVault, vaultVersion } = useSession();
  const [refreshKey, setRefreshKey] = useState(0);
  const [view, setView] = useState<View>({ kind: 'all' });
  const [changingPassword, setChangingPassword] = useState(false);
  const [unlocking, setUnlocking] = useState<VaultEntry | null>(null);
  const [vaultDialog, setVaultDialog] = useState<'new' | 'manage' | null>(null);
  const [counts, setCounts] = useState({ files: 0, collections: 0 });
  const bump = () => setRefreshKey((k) => k + 1);

  // Skip the first run: this effect exists to reset the view and force a
  // reload when the vault changes, not on initial mount (FileList already
  // loads once on mount via its own effect).
  const firstRun = useRef(true);
  useEffect(() => {
    if (firstRun.current) {
      firstRun.current = false;
      return;
    }
    setView({ kind: 'all' });
    setRefreshKey((k) => k + 1);
  }, [vaultVersion]);

  return (
    <AppShell
      banner={
        rotationInterrupted ? (
          <Banner
            status="warning"
            container="section"
            title="A vault password change was interrupted."
            endContent={<Button label="Resume" size="sm" onClick={() => setChangingPassword(true)} />}
          />
        ) : undefined
      }
      sideNav={
        <CollectionSidebar
          selected={view}
          onSelect={setView}
          refreshKey={refreshKey}
          onChanged={bump}
          onLoaded={(n) => setCounts((c) => ({ ...c, collections: n }))}
          header={
            <VStack gap={2} padding={2}>
              <Wordmark />
              <VaultSwitcher onLocked={setUnlocking} onNew={() => setVaultDialog('new')} onManage={() => setVaultDialog('manage')} />
            </VStack>
          }
        />
      }
    >
      <Layout
        header={
          <LayoutHeader hasDivider padding={4}>
            <VStack gap={3}>
              <HStack gap={2} hAlign="between" vAlign="center" wrap="wrap">
                <HStack gap={2} vAlign="end">
                  <Heading level={1}>{viewTitle(view)}</Heading>
                  {activeVault && <Text color="secondary">{activeVault.name}</Text>}
                </HStack>
                <HStack gap={1}>
                  <Button
                    label="Change vault password"
                    variant="ghost"
                    size="sm"
                    onClick={() => setChangingPassword(true)}
                  />
                  <Button label="Log out" variant="ghost" size="sm" onClick={() => void logout()} />
                </HStack>
              </HStack>
              <HStack gap={3} vAlign="end" wrap="wrap">
                <TagSearch onSearch={setView} onClear={() => setView({ kind: 'all' })} />
              </HStack>
            </VStack>
          </LayoutHeader>
        }
        content={
          <LayoutContent padding={0}>
            <VStack gap={3} padding={4}>
              {activeVault && (
                <WelcomeCard
                  key={activeVault.vaultId}
                  vaultId={activeVault.vaultId}
                  name={activeVault.name}
                  hasFiles={counts.files > 0}
                  hasCollections={counts.collections > 0}
                />
              )}
              <UploadQueue onUploaded={bump} />
            </VStack>
            <FileList view={view} refreshKey={refreshKey} onLoaded={(n) => setCounts((c) => ({ ...c, files: n }))} />
          </LayoutContent>
        }
      />
      {changingPassword && <ChangeVaultPassword onDone={() => setChangingPassword(false)} />}
      {unlocking && <UnlockVaultDialog vault={unlocking} onClose={() => setUnlocking(null)} />}
      {vaultDialog === 'new' && <NewVaultDialog onClose={() => setVaultDialog(null)} />}
      {vaultDialog === 'manage' && (
        <ManageVaultsDialog
          onClose={() => setVaultDialog(null)}
          onUnlock={(v) => {
            setVaultDialog(null);
            setUnlocking(v);
          }}
          onChangePassword={() => {
            setVaultDialog(null);
            setChangingPassword(true);
          }}
          onNew={() => setVaultDialog('new')}
        />
      )}
    </AppShell>
  );
}
