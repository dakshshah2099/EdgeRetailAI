import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [svelte()],
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
