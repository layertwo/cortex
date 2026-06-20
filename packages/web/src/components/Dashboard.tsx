import { useSession } from '../auth/SessionContext';

export default function Dashboard() {
  const { logout } = useSession();
  return (
    <div style={{ padding: '2rem' }}>
      <h1>Dashboard</h1>
      <p>Your vault is unlocked. File management arrives in the next slice.</p>
      <button onClick={() => logout()}>Log out</button>
    </div>
  );
}
