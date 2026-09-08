import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  base: '/',
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/kpi': 'http://127.0.0.1:8000',
      '/alerts': 'http://127.0.0.1:8000',
      '/heatmap': 'http://127.0.0.1:8000',
      '/system': 'http://127.0.0.1:8000',
      '/video': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000'
    }
  }
});
