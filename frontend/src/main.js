import './app.css';
import { mount } from 'svelte';
import App from './App.svelte';

if (typeof window !== 'undefined' && (window.location.username || window.location.password)) {
  try {
    const cleanUrl = window.location.origin + window.location.pathname + window.location.search + window.location.hash;
    window.history.replaceState(null, '', cleanUrl);
  } catch {
    // Ignore
  }
}

const app = mount(App, {
  target: document.getElementById('app'),
});

export default app;
