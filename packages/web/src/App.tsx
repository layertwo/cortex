import { ShareAccess } from './components/ShareAccess';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function App() {
  if (window.location.pathname.startsWith('/s')) {
    return <ShareAccess apiBaseUrl={API_BASE_URL} />;
  }

  return (
    <div style={{ padding: '2rem' }}>
      <h1>Cortex</h1>
      <p>Zero-Knowledge Media Backup</p>
    </div>
  );
}

export default App;
