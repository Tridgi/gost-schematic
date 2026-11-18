import React from 'react';
import { createRoot } from 'react-dom/client';
import '@mantine/core/styles.css';
import App from './App';
import './app.css';

const root = document.getElementById('root');
if (!root) throw new Error('APP_ROOT_MISSING');
createRoot(root).render(<React.StrictMode><App /></React.StrictMode>);
