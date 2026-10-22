import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Theme } from '@astryxdesign/core/theme';
import { LinkProvider } from '@astryxdesign/core/Link';
import { cortexTheme } from './theme/cortex';
import { SessionProvider, useSession } from './auth/SessionContext';
import { RequireAuth, RequireVault } from './auth/guards';
import RouterLink from './components/common/RouterLink';
import SignIn from './components/SignIn';
import VaultSetup from './components/VaultSetup';
import VaultUnlock from './components/VaultUnlock';
import RecoverVault from './components/RecoverVault';
import Dashboard from './components/Dashboard';
import { ShareAccess } from './components/ShareAccess';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

// "/" is the dashboard once OIDC sign-in has resolved. A signedOut status means there is
// no (or an expired) provider session, so offer sign-in.
function Home() {
  const { status } = useSession();
  if (status === 'signedOut') return <SignIn />;
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
