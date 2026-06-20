import React from 'react';
import ReactDOM from 'react-dom/client';
import { Amplify } from 'aws-amplify';
import App from './App';
import { getConfig } from './config';

const c = getConfig();
Amplify.configure({
  Auth: { Cognito: { userPoolId: c.userPoolId, userPoolClientId: c.userPoolClientId } },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
