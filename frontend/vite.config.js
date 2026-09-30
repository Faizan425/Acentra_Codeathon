import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The console talks to the FastAPI backend directly (CORS is enabled there for
// local development). VITE_API_URL is injected by docker-compose.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
  },
  preview: {
    host: '0.0.0.0',
    port: 5173,
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.js'],
  },
});
