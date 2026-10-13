import react from '@vitejs/plugin-react';
import { loadEnv } from 'vite';
import { defineConfig } from 'vitest/config';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', 'DOCERE_');
  return {
    plugins: [react()],
    optimizeDeps: {
      exclude: ['lucide-react'],
    },
    test: {
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
      clearMocks: true,
      exclude: ['e2e/**', '**/dist/**', '**/node_modules/**'],
    },
    server: {
      proxy: {
        '/api': {
          target: env.DOCERE_DEV_API_URL ?? 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  };
});
