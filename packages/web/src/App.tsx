import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Theme } from '@astryxdesign/core/theme';
import { LinkProvider } from '@astryxdesign/core/Link';
import { cortexTheme } from './theme/cortex';
import { SessionProvider, useSession } from './auth/SessionContext';
import { RequireAuth, RequireVault } from './auth/guards';
import RouterLink from './components/common/RouterLink';
import Landing from './components/Landing';
import Signup from './components/Signup';
import VerifyEmail from './components/VerifyEmail';
import Login from './components/Login';
import ForgotPassword from './components/ForgotPassword';
import VaultSetup from './components/VaultSetup';
import VaultUnlock from './components/VaultUnlock';
import RecoverVault from './components/RecoverVault';
import Dashboard from './components/Dashboard';
import { ShareAccess } from './components/ShareAccess';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

// "/" is the hero for visitors and the dashboard for everyone with a session.
function Home() {
  const { status } = useSession();
  if (status === 'signedOut') return <Landing />;
  return (
    <RequireAuth>
      <RequireVault>
        <Dashboard />
      </RequireVault>
    </RequireAuth>
  );
}

export default function App() {
  return (
    <Theme theme={cortexTheme}>
      <SessionProvider>
        <BrowserRouter>
          <LinkProvider component={RouterLink}>
            <Routes>
              <Route path="/s/*" element={<ShareAccess apiBaseUrl={API_BASE_URL} />} />
              <Route path="/signup" element={<Signup />} />
              <Route path="/verify" element={<VerifyEmail />} />
              <Route path="/login" element={<Login />} />
              <Route path="/forgot" element={<ForgotPassword />} />
              <Route
                path="/vault/setup"
                element={
                  <RequireAuth>
                    <VaultSetup />
                  </RequireAuth>
                }
              />
              <Route
                path="/vault/unlock"
                element={
                  <RequireAuth>
                    <VaultUnlock />
                  </RequireAuth>
                }
              />
              <Route
                path="/vault/recover"
                element={
                  <RequireAuth>
                    <RecoverVault />
                  </RequireAuth>
                }
              />
              <Route path="/" element={<Home />} />
            </Routes>
          </LinkProvider>
        </BrowserRouter>
      </SessionProvider>
    </Theme>
  );
}
