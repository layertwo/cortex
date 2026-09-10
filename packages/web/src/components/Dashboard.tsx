import { useState } from 'react';
import { AppShell } from '@astryxdesign/core/AppShell';
import { Layout, LayoutHeader, LayoutContent } from '@astryxdesign/core/Layout';
import { Heading } from '@astryxdesign/core/Heading';
import { Button } from '@astryxdesign/core/Button';
import { Banner } from '@astryxdesign/core/Banner';
import { VStack } from '@astryxdesign/core/VStack';
import { HStack } from '@astryxdesign/core/HStack';
import { useSession } from '../auth/SessionContext';
import FileUpload from './FileUpload';
import FileList from './FileList';
import CollectionSidebar, { type View } from './CollectionSidebar';
import TagSearch from './TagSearch';
import ChangeVaultPassword from './ChangeVaultPassword';

function viewTitle(view: View): string {
  if (view.kind === 'collection') return view.name;
  if (view.kind === 'tag') return `Tag: ${view.label}`;
  return 'All files';
}

export default function Dashboard() {
  const { logout, rotationInterrupted } = useSession();
  const [refreshKey, setRefreshKey] = useState(0);
  const [view, setView] = useState<View>({ kind: 'all' });
  const [changingPassword, setChangingPassword] = useState(false);
  const bump = () => setRefreshKey((k) => k + 1);

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
        <CollectionSidebar selected={view} onSelect={setView} refreshKey={refreshKey} onChanged={bump} />
      }
    >
      <Layout
        header={
          <LayoutHeader hasDivider padding={4}>
            <VStack gap={3}>
              <HStack gap={2} hAlign="between" vAlign="center" wrap="wrap">
                <Heading level={1}>{viewTitle(view)}</Heading>
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
                <FileUpload onUploaded={bump} />
              </HStack>
            </VStack>
          </LayoutHeader>
        }
        content={
          <LayoutContent padding={0}>
            <FileList view={view} refreshKey={refreshKey} />
          </LayoutContent>
        }
      />
      {changingPassword && <ChangeVaultPassword onDone={() => setChangingPassword(false)} />}
    </AppShell>
  );
}
