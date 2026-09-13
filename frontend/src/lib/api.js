const API_BASE = import.meta.env.VITE_API_URL || '';

export async function fetchKPIFootfall(params = {}, options = {}) {
  const search = new URLSearchParams();
  if (params.zone_id) search.set('zone_id', params.zone_id);
  if (params.since) search.set('since', params.since);
  if (params.group_by) search.set('group_by', params.group_by);
  if (params.limit) search.set('limit', String(params.limit));

  const query = search.toString() ? `?${search.toString()}` : '';
  const res = await fetch(`${API_BASE}/kpi/footfall${query}`, { signal: options.signal || params.signal });
  if (!res.ok) throw new Error(`Footfall KPI error: ${res.statusText}`);
  return res.json();
}

export async function fetchKPIQueue(params = {}, options = {}) {
  const search = new URLSearchParams();
  if (params.counter_id) search.set('counter_id', params.counter_id);
  if (params.limit) search.set('limit', String(params.limit));

  const query = search.toString() ? `?${search.toString()}` : '';
  const res = await fetch(`${API_BASE}/kpi/queue${query}`, { signal: options.signal || params.signal });
  if (!res.ok) throw new Error(`Queue KPI error: ${res.statusText}`);
  return res.json();
}

export async function fetchKPIStock(params = {}, options = {}) {
  const search = new URLSearchParams();
  if (params.shelf_id) search.set('shelf_id', params.shelf_id);
  if (params.limit) search.set('limit', String(params.limit));

  const query = search.toString() ? `?${search.toString()}` : '';
  const res = await fetch(`${API_BASE}/kpi/stock${query}`, { signal: options.signal || params.signal });
  if (!res.ok) throw new Error(`Stock KPI error: ${res.statusText}`);
  return res.json();
}

export async function fetchKPISKU(params = {}, options = {}) {
  const res = await fetch(`${API_BASE}/kpi/sku`, { signal: options.signal || params.signal });
  if (!res.ok) throw new Error(`SKU KPI error: ${res.statusText}`);
  return res.json();
}

export async function fetchSKUCatalog(params = {}, options = {}) {
  const res = await fetch(`${API_BASE}/kpi/sku/catalog`, { signal: options.signal || params.signal });
  if (!res.ok) throw new Error(`SKU catalog error: ${res.statusText}`);
  return res.json();
}

export async function fetchAlerts(params = {}, options = {}) {
  const search = new URLSearchParams();
  if (params.status) search.set('status', params.status);
  if (params.limit) search.set('limit', String(params.limit));

  const query = search.toString() ? `?${search.toString()}` : '';
  const res = await fetch(`${API_BASE}/alerts${query}`, { signal: options.signal || params.signal });
  if (!res.ok) throw new Error(`Alerts error: ${res.statusText}`);
  return res.json();
}

export async function fetchAlertAudit(params = {}, options = {}) {
  const search = new URLSearchParams();
  if (params.zone_id) search.set('zone_id', params.zone_id);
  if (params.alert_id) search.set('alert_id', params.alert_id);
  if (params.limit) search.set('limit', String(params.limit));

  const query = search.toString() ? `?${search.toString()}` : '';
  const res = await fetch(`${API_BASE}/alerts/audit${query}`, { signal: options.signal || params.signal });
  if (!res.ok) throw new Error(`Alert audit error: ${res.statusText}`);
  return res.json();
}

export async function fetchHeatmap(params = {}, options = {}) {
  const search = new URLSearchParams();
  if (params.zone_id) search.set('zone_id', params.zone_id);
  if (params.since) search.set('since', params.since);
  if (params.cell_size) search.set('cell_size', String(params.cell_size));
  if (params.width) search.set('width', String(params.width));
  if (params.height) search.set('height', String(params.height));
  if (params.limit) search.set('limit', String(params.limit));

  const query = search.toString() ? `?${search.toString()}` : '';
  const res = await fetch(`${API_BASE}/heatmap${query}`, { signal: options.signal || params.signal });
  if (!res.ok) throw new Error(`Heatmap error: ${res.statusText}`);
  return res.json();
}

export async function fetchSystemEnv(options = {}) {
  const res = await fetch(`${API_BASE}/system/env`, { signal: options.signal });
  if (!res.ok) throw new Error(`System env error: ${res.statusText}`);
  return res.json();
}

export async function updateSystemEnv(variables, options = {}) {
  const res = await fetch(`${API_BASE}/system/env`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ variables }),
    signal: options.signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Failed to update environment variables');
  }
  return res.json();
}

export async function toggleDebugMode(options = {}) {
  const res = await fetch(`${API_BASE}/system/toggle-debug`, {
    method: 'POST',
    signal: options.signal,
  });
  if (!res.ok) throw new Error(`Toggle debug error: ${res.statusText}`);
  return res.json();
}

export async function fetchSystemZones(options = {}) {
  const res = await fetch(`${API_BASE}/system/zones`, { signal: options.signal });
  if (!res.ok) throw new Error(`Fetch zones error: ${res.statusText}`);
  return res.json();
}

export async function updateSystemZones(zones, options = {}) {
  const res = await fetch(`${API_BASE}/system/zones`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ zones }),
    signal: options.signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Failed to update zones');
  }
  return res.json();
}

export async function checkHealth(options = {}) {
  try {
    const signal = options.signal || AbortSignal.timeout(3000);
    const res = await fetch(`${API_BASE}/health`, { signal });
    return res.ok;
  } catch {
    return false;
  }
}

export async function fetchPlanogramCompliance(zoneId, options = {}) {
  const res = await fetch(`${API_BASE}/kpi/planogram?zone_id=${encodeURIComponent(zoneId)}`, {
    signal: options.signal,
  });
  if (!res.ok) throw new Error(`Planogram KPI error: ${res.statusText}`);
  return res.json();
}

export async function fetchKPIStaff(params = {}, options = {}) {
  const search = new URLSearchParams();
  if (params.since) search.set('since', params.since);
  if (params.until) search.set('until', params.until);

  const query = search.toString() ? `?${search.toString()}` : '';
  const res = await fetch(`${API_BASE}/kpi/staff${query}`, { signal: options.signal });
  if (!res.ok) throw new Error(`Staff KPI error: ${res.statusText}`);
  return res.json();
}

export function getDailyReportDownloadUrl(dateStr, format = 'csv') {
  return `${API_BASE}/reports/daily?date=${encodeURIComponent(dateStr)}&format=${encodeURIComponent(format)}`;
}

export async function resetTelemetry(options = {}) {
  const res = await fetch(`${API_BASE}/kpi/reset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal: options.signal || AbortSignal.timeout(10000),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Failed to reset telemetry');
  }
  return res.json();
}

export async function resolveAllAlerts(options = {}) {
  const res = await fetch(`${API_BASE}/alerts/resolve-all`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal: options.signal || AbortSignal.timeout(10000),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Failed to resolve alerts');
  }
  return res.json();
}

