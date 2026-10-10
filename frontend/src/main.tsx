import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { PageErrorBoundary } from './components/common/PageErrorBoundary';
import { MotionConfig } from 'framer-motion';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MotionConfig reducedMotion="user">
    <BrowserRouter>
      <PageErrorBoundary><App /></PageErrorBoundary>
    </BrowserRouter>
    </MotionConfig>
  </StrictMode>
);
