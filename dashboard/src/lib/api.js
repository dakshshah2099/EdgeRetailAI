const API_BASE = import.meta.env.VITE_API_URL || '';

export async function fetchKPIFootfall(params = {}) {
  const search = new URLSearchParams();
  if (params.zone_id) search.set('zone_id', params.zone_id);
  if (params.since) search.set('since', params.since);
  if (params.group_by) search.set('group_by', params.group_by);
  if (params.limit) search.set('limit', String(params.limit));

  const query = search.toString() ? `?${search.toString()}` : '';
  const res = await fetch(`${API_BASE}/kpi/footfall${query}`);
  if (!res.ok) throw new Error(`Footfall KPI error: ${res.statusText}`);
  return res.json();
}

export async function fetchKPIQueue(params = {}) {
  const search = new URLSearchParams();
  if (params.counter_id) search.set('counter_id', params.counter_id);
  if (params.limit) search.set('limit', String(params.limit));

  const query = search.toString() ? `?${search.toString()}` : '';
  const res = await fetch(`${API_BASE}/kpi/queue${query}`);
  if (!res.ok) throw new Error(`Queue KPI error: ${res.statusText}`);
  return res.json();
}

export async function fetchKPIStock(params = {}) {
  const search = new URLSearchParams();
  if (params.shelf_id) search.set('shelf_id', params.shelf_id);
  if (params.limit) search.set('limit', String(params.limit));

  const query = search.toString() ? `?${search.toString()}` : '';
  const res = await fetch(`${API_BASE}/kpi/stock${query}`);
  if (!res.ok) throw new Error(`Stock KPI error: ${res.statusText}`);
  return res.json();
}

export async function fetchAlerts(params = {}) {
  const search = new URLSearchParams();
  if (params.status) search.set('status', params.status);
  if (params.limit) search.set('limit', String(params.limit));

  const query = search.toString() ? `?${search.toString()}` : '';
  const res = await fetch(`${API_BASE}/alerts${query}`);
  if (!res.ok) throw new Error(`Alerts error: ${res.statusText}`);
  return res.json();
}

export async function fetchHeatmap(params = {}) {
  const search = new URLSearchParams();
  if (params.zone_id) search.set('zone_id', params.zone_id);
  if (params.since) search.set('since', params.since);
  if (params.cell_size) search.set('cell_size', String(params.cell_size));
  if (params.width) search.set('width', String(params.width));
  if (params.height) search.set('height', String(params.height));
  if (params.limit) search.set('limit', String(params.limit));

  const query = search.toString() ? `?${search.toString()}` : '';
  const res = await fetch(`${API_BASE}/heatmap${query}`);
  if (!res.ok) throw new Error(`Heatmap error: ${res.statusText}`);
  return res.json();
}

export async function fetchSystemEnv() {
  const res = await fetch(`${API_BASE}/system/env`);
  if (!res.ok) throw new Error(`System env error: ${res.statusText}`);
  return res.json();
}

export async function updateSystemEnv(variables) {
  const res = await fetch(`${API_BASE}/system/env`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ variables }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Failed to update environment variables');
  }
  return res.json();
}

export async function toggleDebugMode() {
  const res = await fetch(`${API_BASE}/system/toggle-debug`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Toggle debug error: ${res.statusText}`);
  return res.json();
}

export async function fetchSystemZones() {
  const res = await fetch(`${API_BASE}/system/zones`);
  if (!res.ok) throw new Error(`Fetch zones error: ${res.statusText}`);
  return res.json();
}

export async function updateSystemZones(zones) {
  const res = await fetch(`${API_BASE}/system/zones`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ zones }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Failed to update zones');
  }
  return res.json();
}

export async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
    return res.ok;
  } catch {
    return false;
  }
}
