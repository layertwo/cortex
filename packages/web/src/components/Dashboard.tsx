import { useState } from 'react';
import { useSession } from '../auth/SessionContext';
import FileUpload from './FileUpload';
import FileList from './FileList';

export default function Dashboard() {
  const { logout } = useSession();
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div style={{ padding: '2rem' }}>
      <h1>Dashboard</h1>
      <FileUpload onUploaded={() => setRefreshKey((k) => k + 1)} />
      <FileList refreshKey={refreshKey} />
      <button onClick={() => logout()}>Log out</button>
    </div>
  );
}
