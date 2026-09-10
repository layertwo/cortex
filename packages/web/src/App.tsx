import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Theme } from '@astryxdesign/core/theme';
import { LinkProvider } from '@astryxdesign/core/Link';
import { neutralTheme } from '@astryxdesign/theme-neutral/built';
import { SessionProvider } from './auth/SessionContext';
import { RequireAuth, RequireVault } from './auth/guards';
import RouterLink from './components/common/RouterLink';
import Signup from './components/Signup';
import VerifyEmail from './components/VerifyEmail';
import Login from './components/Login';
import ForgotPassword from './components/ForgotPassword';
import VaultSetup from './components/VaultSetup';
import VaultUnlock from './components/VaultUnlock';
import Dashboard from './components/Dashboard';
import { ShareAccess } from './components/ShareAccess';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export default function App() {
  return (
    <Theme theme={neutralTheme}>
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
                path="/"
                element={
                  <RequireAuth>
                    <RequireVault>
                      <Dashboard />
                    </RequireVault>
                  </RequireAuth>
                }
              />
            </Routes>
          </LinkProvider>
        </BrowserRouter>
      </SessionProvider>
    </Theme>
  );
}
