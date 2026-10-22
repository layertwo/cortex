import React from 'react';
import ReactDOM from 'react-dom/client';
// Order matters: reset (@layer reset) → components (@layer astryx-base) → theme (@layer astryx-theme).
import '@astryxdesign/core/reset.css';
import '@astryxdesign/core/astryx.css';
import './theme/cortex.css';
// Self-hosted Inter (family name "Inter Variable"); no third-party font requests.
import '@fontsource-variable/inter';
import './app.css';
import App from './App';
import { loadConfig } from './config';

loadConfig().then(
  () => {
    ReactDOM.createRoot(document.getElementById('root')!).render(
      <React.StrictMode>
        <App />
      </React.StrictMode>
    );
  },
  (error: unknown) => {
    document.getElementById('root')!.textContent =
      error instanceof Error ? error.message : 'Cortex is unavailable';
  }
);
