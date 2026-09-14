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

export async function fetchSystemZones(params = {}, options = {}) {
  const search = new URLSearchParams();
  if (params && params.frame_w) search.set('frame_w', String(params.frame_w));
  if (params && params.frame_h) search.set('frame_h', String(params.frame_h));

  const query = search.toString() ? `?${search.toString()}` : '';
  const signal = options.signal || (params && params.signal);
  const res = await fetch(`${API_BASE}/system/zones${query}`, { signal });
  if (!res.ok) throw new Error(`Fetch zones error: ${res.statusText}`);

  const calW = parseInt(res.headers.get('x-calibration-width') || '640', 10);
  const calH = parseInt(res.headers.get('x-calibration-height') || '480', 10);
  const data = await res.json();
  if (Array.isArray(data)) {
    data.calibration_width = calW;
    data.calibration_height = calH;
  }
  return data;
}

export async function updateSystemZones(zones, calibrationWidth = null, calibrationHeight = null, options = {}) {
  const payload = { zones };
  if (calibrationWidth) payload.calibration_width = calibrationWidth;
  if (calibrationHeight) payload.calibration_height = calibrationHeight;

  const res = await fetch(`${API_BASE}/system/zones`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal: options.signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Failed to update zones');
  }
  const calW = parseInt(res.headers.get('x-calibration-width') || String(calibrationWidth || 640), 10);
  const calH = parseInt(res.headers.get('x-calibration-height') || String(calibrationHeight || 480), 10);
  const data = await res.json();
  if (Array.isArray(data)) {
    data.calibration_width = calW;
    data.calibration_height = calH;
  }
  return data;
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

export async function resolveAlert(alertId, options = {}) {
  const res = await fetch(`${API_BASE}/alerts/${encodeURIComponent(alertId)}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal: options.signal || AbortSignal.timeout(10000),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Failed to resolve alert');
  }
  return res.json();
}

export async function fetchCameras(options = {}) {
  const res = await fetch(`${API_BASE}/video/cameras`, { signal: options.signal });
  if (!res.ok) throw new Error(`Fetch cameras error: ${res.statusText}`);
  return res.json();
}

export async function registerCamera(cameraData, options = {}) {
  const res = await fetch(`${API_BASE}/video/cameras`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cameraData),
    signal: options.signal || AbortSignal.timeout(10000),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Failed to register camera');
  }
  return res.json();
}

export async function unregisterCamera(cameraId, options = {}) {
  const res = await fetch(`${API_BASE}/video/cameras/${encodeURIComponent(cameraId)}`, {
    method: 'DELETE',
    signal: options.signal || AbortSignal.timeout(10000),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Failed to unregister camera');
  }
  return res.json();
}

export function connectTelemetryWebSocket(onMessage, onStatusChange) {
  let ws = null;
  let isClosedManually = false;
  let retryCount = 0;
  let pingInterval = null;

  const getWsUrl = () => {
    if (typeof window === 'undefined') return '';
    const loc = window.location;
    let url = API_BASE;
    if (!url) {
      const proto = loc.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${proto}//${loc.host}/ws/telemetry`;
    }
    return url.replace(/^http/, 'ws') + '/ws/telemetry';
  };

  function connect() {
    if (isClosedManually || typeof window === 'undefined') return;
    try {
      const wsUrl = getWsUrl();
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        retryCount = 0;
        if (onStatusChange) onStatusChange({ connected: true });
        if (pingInterval) clearInterval(pingInterval);
        pingInterval = setInterval(() => {
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 15000);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'pong') return;
          if (onMessage) onMessage(data);
        } catch (e) {
          console.warn('Failed to parse WS payload', e);
        }
      };

      ws.onclose = () => {
        if (pingInterval) clearInterval(pingInterval);
        if (onStatusChange) onStatusChange({ connected: false });
        if (!isClosedManually) {
          const backoff = Math.min(1000 * Math.pow(2, retryCount), 10000);
          retryCount++;
          setTimeout(connect, backoff);
        }
      };

      ws.onerror = () => {
        ws?.close();
      };
    } catch (e) {
      console.warn('WS connection setup error', e);
      if (!isClosedManually) {
        setTimeout(connect, 3000);
      }
    }
  }

  connect();

  return {
    disconnect() {
      isClosedManually = true;
      if (pingInterval) clearInterval(pingInterval);
      if (ws) ws.close();
    },
    send(payload) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(typeof payload === 'string' ? payload : JSON.stringify(payload));
      }
    },
  };
}

export async function fetchCentralStores(options = {}) {
  try {
    const res = await fetch(`${API_BASE}/central/api/stores`, { signal: options.signal });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

