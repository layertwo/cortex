import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { SessionProvider } from './auth/SessionContext';
import { RequireAuth, RequireVault } from './auth/guards';
import Signup from './components/Signup';
import VerifyEmail from './components/VerifyEmail';
import Login from './components/Login';
import VaultSetup from './components/VaultSetup';
import VaultUnlock from './components/VaultUnlock';
import Dashboard from './components/Dashboard';
import { ShareAccess } from './components/ShareAccess';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export default function App() {
  return (
    <SessionProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/s/*" element={<ShareAccess apiBaseUrl={API_BASE_URL} />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/verify" element={<VerifyEmail />} />
          <Route path="/login" element={<Login />} />
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
      </BrowserRouter>
    </SessionProvider>
  );
}
