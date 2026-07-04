import { useState } from 'react';
import { useSession } from '../auth/SessionContext';
import FileUpload from './FileUpload';
import FileList from './FileList';
import CollectionSidebar, { type View } from './CollectionSidebar';
import TagSearch from './TagSearch';
import ChangeVaultPassword from './ChangeVaultPassword';

export default function Dashboard() {
  const { logout, rotationInterrupted } = useSession();
  const [refreshKey, setRefreshKey] = useState(0);
  const [view, setView] = useState<View>({ kind: 'all' });
  const [changingPassword, setChangingPassword] = useState(false);
  const bump = () => setRefreshKey((k) => k + 1);

  if (changingPassword) {
    return <ChangeVaultPassword onDone={() => setChangingPassword(false)} />;
  }

  return (
    <div style={{ padding: '2rem', display: 'flex', gap: '2rem' }}>
      <CollectionSidebar selected={view} onSelect={setView} refreshKey={refreshKey} onChanged={bump} />
      <div style={{ flex: 1 }}>
        <h1>Dashboard</h1>
        {rotationInterrupted && (
          <p role="alert">
            A vault password change was interrupted.{' '}
            <button onClick={() => setChangingPassword(true)}>Resume</button>
          </p>
        )}
        <FileUpload onUploaded={bump} />
        <TagSearch onSearch={setView} onClear={() => setView({ kind: 'all' })} />
        <FileList view={view} refreshKey={refreshKey} />
        <button onClick={() => setChangingPassword(true)}>Change vault password</button>
        <button onClick={() => logout()}>Log out</button>
      </div>
    </div>
  );
}
