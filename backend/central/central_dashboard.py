import asyncio
import contextlib
import os
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, status
from fastapi import Path as PathParam
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from api.schemas_api import CentralFootfallSummary, CentralStoreStatus, CentralSummaryResponse
from central.aggregator import CrossStoreSummary, aggregate_stores
from central.store_registry import (
    StoreConfig,
    add_store_to_registry,
    load_store_registry,
    remove_store_from_registry,
    resolve_store_config_path,
)


class AddStoreRequest(BaseModel):
    store_id: str = Field(
        min_length=1, max_length=64, description="Unique alphanumeric store identifier"
    )
    name: str = Field(min_length=1, max_length=128, description="Human-readable store name")
    api_base_url: str = Field(
        min_length=7, description="Base URL of store API (e.g. http://127.0.0.1:8000)"
    )



class StoreActionResponse(BaseModel):
    status: str
    message: str
    store: StoreConfig | None = None
    stores: list[StoreConfig]


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Central Store Operations Monitor</title>
  <style>
    :root {
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --border: #e2e8f0;
      --border-dark: #cbd5e1;
      --text: #0f172a;
      --muted: #64748b;
      --primary: #0284c7;
      --primary-hover: #0369a1;
      --emerald-bg: #ecfdf5;
      --emerald-border: #a7f3d0;
      --emerald-text: #065f46;
      --rose-bg: #fff1f2;
      --rose-border: #fecdd3;
      --rose-text: #9f1239;
      --amber-bg: #fffbeb;
      --amber-border: #fde68a;
      --amber-text: #92400e;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      -webkit-font-smoothing: antialiased;
    }

    header {
      background: #ffffff;
      border-bottom: 1px solid var(--border);
      padding: 0.85rem 1.5rem;
      position: sticky;
      top: 0;
      z-index: 30;
      box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03);
    }
    .header-inner {
      max-width: 1400px;
      margin: 0 auto;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .brand-icon {
      width: 32px;
      height: 32px;
      background: #0284c7;
      color: #ffffff;
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: bold;
      font-size: 1rem;
    }
    .brand-title {
      font-size: 1.05rem;
      font-weight: 700;
      color: var(--text);
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .badge-sub {
      font-size: 0.65rem;
      font-family: monospace;
      padding: 0.15rem 0.45rem;
      border-radius: 4px;
      background: #f1f5f9;
      border: 1px solid #cbd5e1;
      color: #475569;
      font-weight: 600;
      letter-spacing: 0.05em;
    }
    .controls {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      font-size: 0.75rem;
      font-family: monospace;
    }
    .refresh-select {
      background: #ffffff;
      border: 1px solid var(--border);
      color: var(--text);
      padding: 0.3rem 0.6rem;
      border-radius: 4px;
      font-size: 0.75rem;
      outline: none;
      cursor: pointer;
    }
    .btn-refresh {
      background: #0284c7;
      color: #ffffff;
      border: none;
      padding: 0.35rem 0.75rem;
      border-radius: 4px;
      cursor: pointer;
      font-weight: 600;
      font-family: monospace;
      font-size: 0.75rem;
      transition: background 0.15s;
    }
    .btn-refresh:hover { background: var(--primary-hover); }
    .last-sync {
      color: var(--muted);
      font-size: 0.72rem;
    }

    main {
      max-width: 1400px;
      margin: 1.5rem auto;
      padding: 0 1.5rem;
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
    }

    /* Fleet KPI Ribbon */
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1rem;
    }
    .kpi-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1rem 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 0.35rem;
      box-shadow: 0 1px 3px 0 rgba(0,0,0,0.02);
    }
    .kpi-label {
      font-size: 0.7rem;
      font-family: monospace;
      text-transform: uppercase;
      color: var(--muted);
      letter-spacing: 0.05em;
      font-weight: 600;
    }
    .kpi-val {
      font-size: 1.5rem;
      font-weight: 800;
      color: var(--text);
      font-family: monospace;
    }
    .kpi-sub {
      font-size: 0.72rem;
      color: var(--muted);
    }

    /* Filters & Search */
    .filter-bar {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 0.75rem;
      background: #ffffff;
      padding: 0.75rem 1rem;
      border: 1px solid var(--border);
      border-radius: 6px;
    }
    .tabs {
      display: flex;
      gap: 0.5rem;
      flex-wrap: wrap;
    }
    .tab-btn {
      background: transparent;
      border: 1px solid transparent;
      padding: 0.25rem 0.65rem;
      border-radius: 4px;
      font-size: 0.75rem;
      font-family: monospace;
      color: var(--muted);
      cursor: pointer;
      font-weight: 600;
      transition: all 0.15s;
    }
    .tab-btn.active {
      background: #f1f5f9;
      border-color: #cbd5e1;
      color: var(--text);
    }
    .search-input {
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 0.35rem 0.65rem;
      font-size: 0.75rem;
      outline: none;
      width: 200px;
      transition: border-color 0.15s;
    }
    .search-input:focus { border-color: var(--primary); }

    .btn-add-store {
      background: #0284c7;
      color: #ffffff;
      border: none;
      padding: 0.35rem 0.85rem;
      border-radius: 4px;
      cursor: pointer;
      font-weight: 600;
      font-family: monospace;
      font-size: 0.75rem;
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      transition: all 0.15s ease;
      box-shadow: 0 1px 2px rgba(2, 132, 199, 0.2);
    }
    .btn-add-store:hover {
      background: #0369a1;
      transform: translateY(-1px);
      box-shadow: 0 3px 6px rgba(2, 132, 199, 0.3);
    }

    /* Store Grid */
    .store-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
      gap: 1.25rem;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      box-shadow: 0 1px 3px 0 rgba(0,0,0,0.02);
      transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
    }
    .card:hover {
      border-color: #94a3b8;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    .card.offline {
      border-color: #fda4af;
      background: #fffafa;
    }
    .card-header {
      padding: 1rem 1.25rem;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 0.5rem;
    }
    .card-title {
      font-size: 1rem;
      font-weight: 700;
      color: var(--text);
    }
    .card-subtitle {
      font-size: 0.72rem;
      font-family: monospace;
      color: var(--muted);
      margin-top: 0.15rem;
    }
    .badge {
      font-size: 0.65rem;
      font-family: monospace;
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
      font-weight: 700;
      letter-spacing: 0.05em;
      white-space: nowrap;
    }
    .badge-online {
      background: var(--emerald-bg);
      border: 1px solid var(--emerald-border);
      color: var(--emerald-text);
    }
    .badge-offline {
      background: var(--rose-bg);
      border: 1px solid var(--rose-border);
      color: var(--rose-text);
    }
    .badge-alert {
      background: var(--amber-bg);
      border: 1px solid var(--amber-border);
      color: var(--amber-text);
    }
    .badge-zero-alert {
      background: #f1f5f9;
      border: 1px solid #e2e8f0;
      color: #64748b;
    }

    .btn-remove-card {
      background: transparent;
      border: 1px solid transparent;
      color: #94a3b8;
      border-radius: 4px;
      padding: 0.2rem 0.35rem;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      transition: all 0.15s ease;
    }
    .btn-remove-card:hover {
      background: #fee2e2;
      border-color: #fecdd3;
      color: #b91c1c;
    }

    .card-body {
      padding: 1rem 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 0.85rem;
      flex: 1;
    }
    .metrics-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.75rem;
    }
    .metric-box {
      background: #f8fafc;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.6rem 0.8rem;
    }
    .metric-box-label {
      font-size: 0.65rem;
      font-family: monospace;
      text-transform: uppercase;
      color: var(--muted);
      font-weight: 600;
    }
    .metric-box-val {
      font-size: 1.15rem;
      font-weight: 800;
      font-family: monospace;
      color: var(--text);
      margin-top: 0.2rem;
    }
    .metric-sub {
      font-size: 0.68rem;
      color: var(--muted);
      margin-top: 0.1rem;
    }

    .status-strip {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.4rem 0.6rem;
      background: #f8fafc;
      border: 1px solid var(--border);
      border-radius: 6px;
      font-size: 0.72rem;
      font-family: monospace;
    }

    .err-container {
      background: var(--rose-bg);
      border: 1px solid var(--rose-border);
      color: var(--rose-text);
      padding: 0.75rem;
      border-radius: 6px;
      font-size: 0.72rem;
      font-family: monospace;
      word-break: break-all;
    }

    .card-footer {
      padding: 0.75rem 1.25rem;
      background: #fcfdfe;
      border-top: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 0.5rem;
    }
    .btn-remove-sm {
      background: transparent;
      border: 1px solid #e2e8f0;
      color: #64748b;
      font-size: 0.72rem;
      font-family: monospace;
      font-weight: 600;
      padding: 0.3rem 0.65rem;
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .btn-remove-sm:hover {
      background: #fff1f2;
      border-color: #fca5a5;
      color: #b91c1c;
    }
    .launch-btn {
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      background: #ffffff;
      border: 1px solid #cbd5e1;
      color: var(--text);
      text-decoration: none;
      font-size: 0.72rem;
      font-family: monospace;
      font-weight: 600;
      padding: 0.3rem 0.65rem;
      border-radius: 4px;
      transition: all 0.15s;
    }
    .launch-btn:hover {
      background: #f1f5f9;
      border-color: #94a3b8;
    }

    .empty-state {
      background: #ffffff;
      border: 1px dashed var(--border-dark);
      border-radius: 8px;
      padding: 3rem 2rem;
      text-align: center;
      color: var(--muted);
      grid-column: 1 / -1;
    }

    /* Modal Styles */
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, 0.55);
      backdrop-filter: blur(4px);
      -webkit-backdrop-filter: blur(4px);
      z-index: 100;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 1.5rem;
      opacity: 0;
      transition: opacity 0.2s ease;
    }
    .modal-backdrop.open {
      display: flex;
      opacity: 1;
    }
    .modal-card {
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 10px;
      max-width: 520px;
      width: 100%;
      box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1);
      overflow: hidden;
      transform: scale(0.96) translateY(10px);
      transition: transform 0.2s ease;
    }
    .modal-backdrop.open .modal-card {
      transform: scale(1) translateY(0);
    }
    .modal-sm {
      max-width: 440px;
    }
    .modal-header {
      padding: 1.25rem 1.5rem;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      background: #f8fafc;
    }
    .modal-title {
      font-size: 1.05rem;
      font-weight: 700;
      color: var(--text);
    }
    .modal-subtitle {
      font-size: 0.75rem;
      color: var(--muted);
      margin-top: 0.2rem;
    }
    .modal-close {
      background: transparent;
      border: none;
      font-size: 1.4rem;
      color: var(--muted);
      cursor: pointer;
      padding: 0 0.4rem;
      line-height: 1;
      border-radius: 4px;
    }
    .modal-close:hover { color: var(--text); background: #e2e8f0; }
    .modal-body {
      padding: 1.5rem;
      display: flex;
      flex-direction: column;
      gap: 1.1rem;
    }
    .modal-footer {
      padding: 1rem 1.5rem;
      background: #f8fafc;
      border-top: 1px solid var(--border);
      display: flex;
      justify-content: flex-end;
      align-items: center;
      gap: 0.75rem;
    }
    .form-group {
      display: flex;
      flex-direction: column;
      gap: 0.35rem;
    }
    .form-label {
      font-size: 0.68rem;
      font-family: monospace;
      font-weight: 700;
      color: var(--muted);
      letter-spacing: 0.05em;
    }
    .form-input {
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.55rem 0.75rem;
      font-size: 0.85rem;
      color: var(--text);
      outline: none;
      transition: border-color 0.15s, box-shadow 0.15s;
    }
    .form-input:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(2, 132, 199, 0.15);
    }
    .form-hint {
      font-size: 0.7rem;
      color: var(--muted);
    }
    .presets-row {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      margin-top: 0.25rem;
    }
    .preset-btn {
      background: #f1f5f9;
      border: 1px solid #cbd5e1;
      color: #334155;
      padding: 0.25rem 0.55rem;
      border-radius: 4px;
      font-size: 0.7rem;
      font-family: monospace;
      cursor: pointer;
      font-weight: 600;
      transition: all 0.15s;
    }
    .preset-btn:hover {
      background: #e2e8f0;
      border-color: #94a3b8;
      color: #0f172a;
    }
    .modal-error {
      background: var(--rose-bg);
      border: 1px solid var(--rose-border);
      color: var(--rose-text);
      padding: 0.65rem 0.85rem;
      border-radius: 6px;
      font-size: 0.78rem;
      font-family: monospace;
    }
    .btn-cancel {
      background: transparent;
      border: 1px solid #cbd5e1;
      color: var(--text);
      padding: 0.45rem 1rem;
      border-radius: 5px;
      font-size: 0.8rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s;
    }
    .btn-cancel:hover { background: #f1f5f9; }
    .btn-primary-action {
      background: var(--primary);
      color: #ffffff;
      border: none;
      padding: 0.45rem 1.25rem;
      border-radius: 5px;
      font-size: 0.8rem;
      font-weight: 700;
      cursor: pointer;
      transition: all 0.15s;
      box-shadow: 0 1px 2px rgba(2, 132, 199, 0.25);
    }
    .btn-primary-action:hover { background: var(--primary-hover); }
    .btn-primary-action:disabled { opacity: 0.6; cursor: not-allowed; }
    .btn-danger-action {
      background: #e11d48;
      color: #ffffff;
      border: none;
      padding: 0.45rem 1.25rem;
      border-radius: 5px;
      font-size: 0.8rem;
      font-weight: 700;
      cursor: pointer;
      transition: all 0.15s;
    }
    .btn-danger-action:hover { background: #be123c; }
    .btn-danger-action:disabled { opacity: 0.6; cursor: not-allowed; }

    /* Toast Notification */
    .toast-container {
      position: fixed;
      bottom: 1.5rem;
      right: 1.5rem;
      z-index: 200;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      pointer-events: none;
    }
    .toast {
      pointer-events: auto;
      min-width: 280px;
      max-width: 420px;
      padding: 0.75rem 1rem;
      border-radius: 6px;
      font-size: 0.8rem;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -4px rgba(0,0,0,0.1);
      display: flex;
      align-items: center;
      gap: 0.6rem;
      animation: toastIn 0.2s ease forwards;
      transition: all 0.2s ease;
    }
    .toast-success {
      background: #064e3b;
      color: #ecfdf5;
      border: 1px solid #059669;
    }
    .toast-error {
      background: #881337;
      color: #fff1f2;
      border: 1px solid #e11d48;
    }
    .toast-info {
      background: #0f172a;
      color: #f8fafc;
      border: 1px solid #334155;
    }
    @keyframes toastIn {
      from { opacity: 0; transform: translateY(12px) scale(0.96); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }
  </style>
</head>
<body>
  <header>
    <div class="header-inner">
      <div class="brand">
        <div class="brand-icon">⚡</div>
        <div>
          <div class="brand-title">
            <span>Central Store Operations Monitor</span>
            <span class="badge-sub">FLEET OPS</span>
            <span class="badge-sub">EDGE AI</span>
          </div>
        </div>
      </div>
      <div class="controls">
        <span class="last-sync" id="last-sync">Syncing...</span>
        <div>
          Auto-refresh:
          <select id="refresh-interval" class="refresh-select" onchange="updateInterval()">
            <option value="3000">3s</option>
            <option value="5000" selected>5s</option>
            <option value="10000">10s</option>
            <option value="0">Off</option>
          </select>
        </div>
        <button class="btn-refresh" onclick="refresh()">Refresh Now</button>
      </div>
    </div>
  </header>

  <main>
    <!-- Fleet KPI Ribbon -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <span class="kpi-label">Fleet Reachability</span>
        <div class="kpi-val" id="kpi-reachability">-</div>
        <div class="kpi-sub" id="kpi-reachability-sub">Checking edge nodes...</div>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">Total In-Store Occupancy</span>
        <div class="kpi-val" id="kpi-occupancy">-</div>
        <div class="kpi-sub" id="kpi-occupancy-sub">Across all active stores</div>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">Fleet Footfall Today</span>
        <div class="kpi-val" id="kpi-footfall">-</div>
        <div class="kpi-sub" id="kpi-footfall-sub">Total enters & exits</div>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">Total Open Alerts</span>
        <div class="kpi-val" id="kpi-alerts">-</div>
        <div class="kpi-sub" id="kpi-alerts-sub">Fleet incident load</div>
      </div>
    </div>

    <!-- Filters & Search & Add Store -->
    <div class="filter-bar">
      <div class="tabs">
        <button class="tab-btn active" onclick="setFilter('all', this)" id="tab-all">
          All Stores (<span id="count-all">0</span>)
        </button>
        <button class="tab-btn" onclick="setFilter('online', this)">
          Online (<span id="count-on">0</span>)
        </button>
        <button class="tab-btn" onclick="setFilter('offline', this)">
          Offline (<span id="count-off">0</span>)
        </button>
        <button class="tab-btn" onclick="setFilter('alerting', this)">
          Alerting (<span id="count-alert">0</span>)
        </button>
      </div>
      <div style="display:flex;align-items:center;gap:0.75rem;flex-wrap:wrap;">
        <input
          type="text"
          id="search-input"
          class="search-input"
          placeholder="Search stores..."
          oninput="handleSearch()"
        />
        <button class="btn-add-store" onclick="openAddModal()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2.5">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          Add Store
        </button>
      </div>
    </div>

    <!-- Store Grid -->
    <div class="store-grid" id="store-grid">
      <div class="empty-state">Polling store registry...</div>
    </div>
  </main>

  <!-- Add Store Modal -->
  <div id="add-modal" class="modal-backdrop" onclick="handleBackdropClick(event, 'add-modal')">
    <div class="modal-card">
      <div class="modal-header">
        <div>
          <div class="modal-title">⚡ Register Store Node</div>
          <div class="modal-subtitle">
            Connect a new edge node deployment to Central Multi-Store Monitoring
          </div>
        </div>
        <button class="modal-close" onclick="closeAddModal()">&times;</button>
      </div>
      <div class="modal-body">
        <div id="modal-error" class="modal-error" style="display:none;"></div>

        <div class="form-group">
          <label class="form-label" for="add-store-id">STORE IDENTIFIER (SLUG)</label>
          <input type="text" id="add-store-id" class="form-input"
                 placeholder="e.g. store_north" oninput="markIdManual()" />
          <div class="form-hint">Unique alphanumeric ID (e.g. store_east, kiosk_terminal_1)</div>
        </div>

        <div class="form-group">
          <label class="form-label" for="add-store-name">STORE DISPLAY NAME</label>
          <input type="text" id="add-store-name" class="form-input"
                 placeholder="e.g. North Flagship Galleria"
                 oninput="autoFillStoreId(this.value)" />
          <div class="form-hint">Friendly name shown on central rollup cards</div>
        </div>

        <div class="form-group">
          <label class="form-label" for="add-store-url">API BASE URL</label>
          <input type="url" id="add-store-url" class="form-input"
                 placeholder="http://127.0.0.1:8003" />
          <div class="form-hint">Root URL where this store node is reachable (HTTP/HTTPS)</div>
        </div>

        <div class="form-group">
          <label class="form-label">QUICK PRESETS</label>
          <div class="presets-row">
            <button type="button" class="preset-btn"
              onclick="applyPreset('store_east', 'Eastside Mall', 'http://127.0.0.1:8003')">
              + Local Node (:8003)
            </button>
            <button type="button" class="preset-btn"
              onclick="applyPreset('store_uptown', 'Uptown Kiosk', 'http://127.0.0.1:8004')">
              + Local Node (:8004)
            </button>
            <button type="button" class="preset-btn"
              onclick="applyPreset('store_pi', 'Edge Pi Device', 'http://192.168.1.150:8000')">
              + Remote Edge Pi
            </button>
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn-cancel" onclick="closeAddModal()">Cancel</button>
        <button id="btn-submit-store" class="btn-primary-action" onclick="submitAddStore()">
          Add Store Node
        </button>
      </div>
    </div>
  </div>

  <!-- Remove Store Confirmation Modal -->
  <div id="confirm-modal" class="modal-backdrop"
       onclick="handleBackdropClick(event, 'confirm-modal')">
    <div class="modal-card modal-sm">
      <div class="modal-header">
        <div>
          <div class="modal-title" style="color:var(--rose-text);">⚠️ Remove Store Node</div>
          <div class="modal-subtitle">Disconnect store from central monitoring</div>
        </div>
        <button class="modal-close" onclick="closeConfirmModal()">&times;</button>
      </div>
      <div class="modal-body">
        <p style="font-size:0.85rem;color:var(--text);margin-bottom:0.75rem;">
          Are you sure you want to remove <strong id="confirm-store-name"></strong>
          (<code id="confirm-store-id"></code>) from Central Monitoring?
        </p>
        <p style="font-size:0.75rem;color:var(--muted);">
          This will delete the store from <code>stores.yaml</code> and stop fleet telemetry.
        </p>
      </div>
      <div class="modal-footer">
        <button class="btn-cancel" onclick="closeConfirmModal()">Cancel</button>
        <button id="btn-confirm-delete" class="btn-danger-action" onclick="executeRemoveStore()">
          Confirm Removal
        </button>
      </div>
    </div>
  </div>

  <!-- Toast Container -->
  <div id="toast-container" class="toast-container"></div>

  <script>
    let rawStores = [];
    let currentFilter = 'all';
    let searchQuery = '';
    let refreshTimer = null;
    let storeToDelete = null;

    function escapeHtml(str) {
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    function escapeJs(str) {
      if (!str) return '';
      return String(str).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"');
    }

    function showToast(msg, type = 'info') {
      const container = document.getElementById('toast-container');
      if (!container) return;
      const t = document.createElement('div');
      t.className = 'toast toast-' + type;
      const icon = type === 'success' ? '✓ ' : type === 'error' ? '✕ ' : 'ℹ ';
      t.innerText = icon + msg;
      container.appendChild(t);
      setTimeout(() => {
        t.style.opacity = '0';
        t.style.transform = 'translateY(8px)';
        setTimeout(() => t.remove(), 250);
      }, 3500);
    }

    function setFilter(filter, el) {
      currentFilter = filter;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      el.classList.add('active');
      render();
    }

    function handleSearch() {
      searchQuery = (document.getElementById('search-input').value || '').toLowerCase().trim();
      render();
    }

    function updateInterval() {
      if (refreshTimer) clearInterval(refreshTimer);
      const val = parseInt(document.getElementById('refresh-interval').value, 10);
      if (val > 0) {
        refreshTimer = setInterval(refresh, val);
      }
    }

    async function loadInitialStores() {
      try {
        const basePath = window.location.pathname.replace(/\/$/, '');
        const res = await fetch(basePath + '/api/stores');
        if (res.ok) {
          const stores = await res.json();
          if (Array.isArray(stores) && rawStores.length === 0) {
            rawStores = stores.map(s => ({
              store_id: s.store_id,
              name: s.name,
              api_base_url: s.api_base_url,
              reachable: false,
              error: 'Connecting to node...',
              footfall: null,
              open_alert_count: null,
              queue_events_count: 0,
              stock_events_count: 0,
            }));
            render();
          }
        }
      } catch (e) {
        console.warn('Initial store list fetch failed', e);
      }
    }

    let isRefreshing = false;

    async function refresh() {
      if (isRefreshing) return;
      isRefreshing = true;
      const syncEl = document.getElementById('last-sync');
      if (syncEl) syncEl.innerText = 'Syncing...';

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 4500);

      try {
        const basePath = window.location.pathname.replace(/\/$/, '');
        const res = await fetch(basePath + '/api/summary', { signal: controller.signal });
        clearTimeout(timeoutId);
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        rawStores = data.stores || [];

        // 1. Calculate Fleet KPIs
        const total = rawStores.length;
        const online = data.total_reachable;
        const offline = data.total_unreachable;
        const pct = total > 0 ? Math.round((online / total) * 100) : 0;

        let totalOccupancy = 0;
        let totalEnters = 0;
        let totalExits = 0;
        let totalAlerts = 0;
        let alertingCount = 0;

        rawStores.forEach(s => {
          if (s.reachable && s.footfall) {
            totalOccupancy += (s.footfall.net_occupancy || 0);
            totalEnters += (s.footfall.total_enters || 0);
            totalExits += (s.footfall.total_exits || 0);
          }
          if (s.open_alert_count) {
            totalAlerts += s.open_alert_count;
            alertingCount++;
          }
        });

        document.getElementById('kpi-reachability').innerText = `${online} / ${total}`;
        document.getElementById('kpi-reachability-sub').innerText = `${pct}% edge nodes online`;

        document.getElementById('kpi-occupancy').innerText = totalOccupancy;
        document.getElementById('kpi-occupancy-sub').innerText = `Across ${online} online nodes`;

        document.getElementById('kpi-footfall').innerText = `↑${totalEnters}  ↓${totalExits}`;
        document.getElementById('kpi-footfall-sub').innerText = `Net +${totalOccupancy} shoppers`;

        document.getElementById('kpi-alerts').innerText = totalAlerts;
        document.getElementById('kpi-alerts-sub').innerText =
          `${alertingCount} stores with active alerts`;

        // Update Tab Counts
        document.getElementById('count-all').innerText = total;
        document.getElementById('count-on').innerText = online;
        document.getElementById('count-off').innerText = offline;
        document.getElementById('count-alert').innerText = alertingCount;

        const now = new Date();
        if (syncEl) syncEl.innerText = 'Last sync: ' + now.toLocaleTimeString();

        render();
      } catch (err) {
        clearTimeout(timeoutId);
        console.error('Failed fetching central summary:', err);
        if (syncEl) {
          syncEl.innerText = err.name === 'AbortError'
            ? 'Sync timed out'
            : 'Sync error: ' + err.message;
        }
        render();
      } finally {
        isRefreshing = false;
      }
    }

    function render() {
      const grid = document.getElementById('store-grid');
      let list = rawStores.slice();

      if (currentFilter === 'online') list = list.filter(s => s.reachable);
      else if (currentFilter === 'offline') list = list.filter(s => !s.reachable);
      else if (currentFilter === 'alerting') {
        list = list.filter(s => s.open_alert_count && s.open_alert_count > 0);
      }

      if (searchQuery) {
        list = list.filter(s =>
          (s.store_id || '').toLowerCase().includes(searchQuery) ||
          (s.name || '').toLowerCase().includes(searchQuery)
        );
      }

      if (list.length === 0) {
        if (rawStores.length === 0) {
          grid.innerHTML = `
            <div class="empty-state">
              <div style="font-size:1.8rem;margin-bottom:0.5rem;">🏪</div>
              <div style="font-weight:700;color:var(--text);margin-bottom:0.35rem;">
                No Store Nodes Configured
              </div>
              <div style="font-size:0.8rem;margin-bottom:1rem;">
                Add an edge store node using the "+ Add Store" button.
              </div>
              <button class="btn-add-store" onclick="openAddModal()">+ Add Your First Store</button>
            </div>
          `;
        } else {
          grid.innerHTML = '<div class="empty-state">No matching store nodes found.</div>';
        }
        return;
      }

      grid.innerHTML = list.map(s => {
        const storeName = s.name || s.store_id;
        const alertCount = s.open_alert_count || 0;
        const alertBadge = alertCount > 0
          ? `<span class="badge badge-alert">${alertCount} ALERTS</span>`
          : `<span class="badge badge-zero-alert">0 ALERTS</span>`;

        return `
          <div class="card ${s.reachable ? '' : 'offline'}">
            <div class="card-header">
              <div>
                <div class="card-title">${escapeHtml(storeName)}</div>
                <div class="card-subtitle">ID: ${escapeHtml(s.store_id)}</div>
              </div>
              <div style="display:flex;align-items:center;gap:0.4rem;">
                <span class="badge ${s.reachable ? 'badge-online' : 'badge-offline'}">
                  ${s.reachable ? 'ONLINE' : 'OFFLINE'}
                </span>
                <button class="btn-remove-card" title="Remove store node"
                  onclick="promptRemoveStore('${escapeJs(s.store_id)}', '${escapeJs(storeName)}')">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
                       stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
                    <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6
                             m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M10 11v6M14 11v6"/>
                  </svg>
                </button>
              </div>
            </div>

            <div class="card-body">
              ${s.reachable ? `
                <div class="metrics-row">
                  <div class="metric-box">
                    <div class="metric-box-label">In-Store Occupancy</div>
                    <div class="metric-box-val">${s.footfall ? s.footfall.net_occupancy : 0}</div>
                    <div class="metric-sub">Live Headcount</div>
                  </div>
                  <div class="metric-box">
                    <div class="metric-box-label">Today's Footfall</div>
                    <div class="metric-box-val">↑${s.footfall ? s.footfall.total_enters : 0}</div>
                    <div class="metric-sub">↓ ${s.footfall ? s.footfall.total_exits : 0} Exits</div>
                  </div>
                </div>

                <div class="status-strip">
                  <span>ACTIVE INCIDENTS:</span>
                  ${alertBadge}
                </div>

                <div class="status-strip">
                  <span>PIPELINE EVENTS:</span>
                  <span>${s.queue_events_count} Queue · ${s.stock_events_count} Stock</span>
                </div>
              ` : `
                <div class="err-container">
                  <strong>CONNECTION FAILURE:</strong><br>
                  ${escapeHtml(s.error || 'Node unreachable. Port closed or network down.')}
                </div>
              `}
            </div>

            <div class="card-footer">
              <span class="card-subtitle">${escapeHtml(s.api_base_url || 'Local Edge Node')}</span>
              <div style="display:flex;align-items:center;gap:0.4rem;">
                <button class="btn-remove-sm"
                  onclick="promptRemoveStore('${escapeJs(s.store_id)}', '${escapeJs(storeName)}')">
                  Remove
                </button>
                ${s.api_base_url ? `
                  <a href="${escapeHtml(s.api_base_url)}" target="_blank"
                     rel="noopener" class="launch-btn">
                    Launch Node ↗
                  </a>
                ` : ''}
              </div>
            </div>
          </div>
        `;
      }).join('');
    }

    /* Modal Management */
    function openAddModal() {
      document.getElementById('modal-error').style.display = 'none';
      document.getElementById('add-store-id').value = '';
      document.getElementById('add-store-id').dataset.manual = 'false';
      document.getElementById('add-store-name').value = '';
      document.getElementById('add-store-url').value = '';
      document.getElementById('add-modal').classList.add('open');
      setTimeout(() => document.getElementById('add-store-name').focus(), 50);
    }

    function closeAddModal() {
      document.getElementById('add-modal').classList.remove('open');
    }

    function markIdManual() {
      document.getElementById('add-store-id').dataset.manual = 'true';
    }

    function autoFillStoreId(nameVal) {
      const idInput = document.getElementById('add-store-id');
      if (idInput.dataset.manual !== 'true') {
        const cleaned = nameVal.toLowerCase().replace(/[^a-z0-9]+/g, '_');
        idInput.value = 'store_' + cleaned.replace(/^_+|_+$/g, '');
      }
    }

    function applyPreset(id, name, url) {
      const idInput = document.getElementById('add-store-id');
      idInput.value = id;
      idInput.dataset.manual = 'true';
      document.getElementById('add-store-name').value = name;
      document.getElementById('add-store-url').value = url;
      document.getElementById('modal-error').style.display = 'none';
    }

    function showModalError(msg) {
      const errBox = document.getElementById('modal-error');
      errBox.innerText = msg;
      errBox.style.display = 'block';
    }

    async function submitAddStore() {
      const errBox = document.getElementById('modal-error');
      errBox.style.display = 'none';

      const storeId = document.getElementById('add-store-id').value.trim();
      const name = document.getElementById('add-store-name').value.trim();
      const url = document.getElementById('add-store-url').value.trim();

      if (!storeId) {
        showModalError('Store identifier (ID) is required');
        return;
      }
      if (!/^[a-zA-Z0-9_-]+$/.test(storeId)) {
        showModalError('Store ID can only contain letters, numbers, hyphens, and underscores');
        return;
      }
      if (!name) {
        showModalError('Store display name is required');
        return;
      }
      if (!url || (!url.startsWith('http://') && !url.startsWith('https://'))) {
        showModalError('API Base URL must start with http:// or https://');
        return;
      }

      const btn = document.getElementById('btn-submit-store');
      btn.disabled = true;
      btn.innerText = 'Registering...';

      try {
        const basePath = window.location.pathname.replace(/\/$/, '');
        const res = await fetch(basePath + '/api/stores', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ store_id: storeId, name: name, api_base_url: url })
        });
        const result = await res.json();
        if (!res.ok) {
          throw new Error(result.detail || result.message || 'Failed adding store');
        }
        closeAddModal();
        showToast(`Store '${name}' registered successfully!`, 'success');
        refresh();
      } catch (err) {
        showModalError(err.message);
      } finally {
        btn.disabled = false;
        btn.innerText = 'Add Store Node';
      }
    }

    function promptRemoveStore(storeId, storeName) {
      storeToDelete = { id: storeId, name: storeName };
      document.getElementById('confirm-store-name').innerText = storeName;
      document.getElementById('confirm-store-id').innerText = storeId;
      document.getElementById('confirm-modal').classList.add('open');
    }

    function closeConfirmModal() {
      document.getElementById('confirm-modal').classList.remove('open');
      storeToDelete = null;
    }

    async function executeRemoveStore() {
      if (!storeToDelete) return;
      const btn = document.getElementById('btn-confirm-delete');
      btn.disabled = true;
      btn.innerText = 'Removing...';

      const { id, name } = storeToDelete;
      try {
        const basePath = window.location.pathname.replace(/\/$/, '');
        const res = await fetch(basePath + '/api/stores/' + encodeURIComponent(id), {
          method: 'DELETE'
        });
        const result = await res.json();
        if (!res.ok) {
          throw new Error(result.detail || result.message || 'Failed removing store');
        }
        closeConfirmModal();
        showToast(`Store '${name}' removed from fleet`, 'success');
        refresh();
      } catch (err) {
        showToast('Failed to remove store: ' + err.message, 'error');
      } finally {
        btn.disabled = false;
        btn.innerText = 'Confirm Removal';
      }
    }

    function handleBackdropClick(event, modalId) {
      if (event.target.id === modalId) {
        if (modalId === 'add-modal') closeAddModal();
        else if (modalId === 'confirm-modal') closeConfirmModal();
      }
    }

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closeAddModal();
        closeConfirmModal();
      } else if (
        e.key === 'Enter' &&
        document.getElementById('add-modal').classList.contains('open')
      ) {
        submitAddStore();
      }
    });

    loadInitialStores().then(() => refresh());
    updateInterval();
  </script>
</body>
</html>
"""


def create_central_app(config_path: str | Path = "stores.yaml") -> FastAPI:
    """Create FastAPI application for centralized multi-store monitoring."""
    app = FastAPI(
        title="Central Multi-Store Retail Intelligence",
        description="Rollup monitoring across distributed edge retail store deployments",
        version="0.3.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_registry() -> list[StoreConfig]:
        path = resolve_store_config_path(config_path)
        if not path.is_file():
            return []
        try:
            return load_store_registry(path)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed loading store registry: {exc}",
            ) from exc

    @app.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/stores", tags=["central"])
    def get_stores() -> list[StoreConfig]:
        return get_registry()

    @app.post(
        "/api/stores",
        status_code=status.HTTP_201_CREATED,
        tags=["central"],
    )
    def add_store(req: AddStoreRequest) -> StoreActionResponse:
        """Register a new store node in stores.yaml."""
        path = resolve_store_config_path(config_path)
        clean_store = StoreConfig(
            store_id=req.store_id.strip(),
            name=req.name.strip(),
            api_base_url=req.api_base_url.strip().rstrip("/"),
        )
        try:
            updated_stores = add_store_to_registry(path, clean_store)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed adding store: {exc}",
            ) from exc

        # Auto-spawn if local loopback and auto-spawning enabled
        if (
            os.environ.get("AUTO_SPAWN_LOCAL_STORES", "true").lower() == "true"
            and "PYTEST_CURRENT_TEST" not in os.environ
        ):
            with contextlib.suppress(Exception):
                from central.store_spawner import spawn_configured_local_stores

                spawn_configured_local_stores(path)

        return StoreActionResponse(
            status="created",
            message=f"Store '{clean_store.name}' ({clean_store.store_id}) registered successfully",
            store=clean_store,
            stores=updated_stores,
        )

    @app.delete(
        "/api/stores/{store_id}",
        tags=["central"],
    )
    def remove_store(
        store_id: Annotated[str, PathParam(description="Store ID to remove from registry")],
    ) -> StoreActionResponse:
        """Remove an edge store node by store_id from stores.yaml."""
        path = resolve_store_config_path(config_path)
        try:
            updated_stores, removed = remove_store_from_registry(path, store_id)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed removing store: {exc}",
            ) from exc

        # Clean up local spawned instance if running
        with contextlib.suppress(Exception):
            from urllib.parse import urlparse

            from central.store_spawner import stop_spawned_store

            parsed = urlparse(removed.api_base_url)
            if parsed.port:
                stop_spawned_store(parsed.port)

        return StoreActionResponse(
            status="deleted",
            message=f"Store '{removed.name}' ({removed.store_id}) removed from fleet registry",
            store=removed,
            stores=updated_stores,
        )

    @app.get("/api/summary", tags=["central"])
    async def get_cross_store_summary() -> CentralSummaryResponse:
        registry = get_registry()
        if (
            os.environ.get("AUTO_SPAWN_LOCAL_STORES", "true").lower() == "true"
            and "PYTEST_CURRENT_TEST" not in os.environ
        ):
            with contextlib.suppress(Exception):
                from central.store_spawner import spawn_configured_local_stores

                await asyncio.to_thread(
                    spawn_configured_local_stores, resolve_store_config_path(config_path)
                )

        summary: CrossStoreSummary = await asyncio.to_thread(aggregate_stores, registry, 2.0)

        stores_data: list[CentralStoreStatus] = []
        for s in summary.stores:
            stores_data.append(
                CentralStoreStatus(
                    store_id=s.store_id,
                    name=s.name,
                    api_base_url=s.api_base_url,
                    reachable=s.reachable,
                    error=s.error,
                    footfall=(
                        CentralFootfallSummary(
                            total_enters=s.footfall_summary.total_enters,
                            total_exits=s.footfall_summary.total_exits,
                            net_occupancy=s.footfall_summary.net_occupancy,
                        )
                        if s.footfall_summary
                        else None
                    ),
                    open_alert_count=s.open_alert_count,
                    queue_events_count=len(s.queue_events) if s.queue_events else 0,
                    stock_events_count=len(s.stock_events) if s.stock_events else 0,
                )
            )

        return CentralSummaryResponse(
            generated_at=summary.generated_at.isoformat(),
            total_reachable=summary.total_reachable,
            total_unreachable=summary.total_unreachable,
            stores=stores_data,
        )

    @app.get("/", response_class=HTMLResponse, tags=["dashboard"])
    async def dashboard_ui() -> str:
        return HTML_TEMPLATE

    @app.get("/central", response_class=HTMLResponse, tags=["dashboard"])
    async def dashboard_ui_central() -> str:
        return HTML_TEMPLATE

    return app


app = create_central_app()
