<script>
  export let isConnected = true;
  export let lastUpdated = new Date();
  export let isRefreshing = false;
  export let autoRefresh = true;
  export let refreshInterval = 3;
  export let selectedTimeRange = 'all';
  export let selectedZone = '';
  export let activeTab = 'camera';
  export let onRefresh = () => {};
  export let onOpenSettings = () => {};

  function formatTime(date) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
</script>

<header class="header">
  <div class="brand">
    <div class="brand-icon">
      <svg viewBox="0 0 24 24" width="22" height="22" stroke="currentColor" stroke-width="2" fill="none">
        <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/>
        <line x1="3" y1="6" x2="21" y2="6"/>
        <path d="M16 10a4 4 0 0 1-8 0"/>
      </svg>
    </div>
    <div class="titles">
      <div class="title-row">
        <h1>Intelligent Retail Analytics</h1>
        <span class="badge edge-badge">Edge AI • SIH26179</span>
      </div>
      <p class="subtitle">On-device customer traffic, checkout queues & shelf inventory intelligence</p>
    </div>
  </div>

  <div class="controls">
    <div class="filter-group">
      <label for="time-range">Range</label>
      <select id="time-range" bind:value={selectedTimeRange} on:change={onRefresh}>
        <option value="all">All Time</option>
        <option value="1h">Last 1 Hour</option>
        <option value="6h">Last 6 Hours</option>
        <option value="24h">Last 24 Hours</option>
      </select>
    </div>

    <div class="filter-group">
      <label for="zone-filter">Zone</label>
      <input 
        id="zone-filter" 
        type="text" 
        placeholder="All Zones..." 
        bind:value={selectedZone} 
        on:input={onRefresh}
      />
    </div>

    <div class="status-indicator" title="Edge server connectivity status">
      <span class="status-dot" class:connected={isConnected}></span>
      <span class="status-text">{isConnected ? 'Edge Connected' : 'Connecting...'}</span>
      <span class="timestamp">{formatTime(lastUpdated)}</span>
    </div>

    <button 
      type="button"
      class="settings-btn" 
      class:active={activeTab === 'settings'} 
      on:click={onOpenSettings}
      title="System Settings & Configuration"
    >
      <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
      </svg>
      <span>Settings</span>
    </button>

    <div class="refresh-controls">
      <label class="auto-refresh-toggle" title="Automatic polling toggle">
        <input type="checkbox" bind:checked={autoRefresh} />
        <span>Auto ({refreshInterval}s)</span>
      </label>
      <button 
        type="button"
        class="refresh-btn" 
        class:spinning={isRefreshing} 
        on:click={onRefresh}
        title="Refresh data now"
        aria-label="Refresh data"
      >
        <svg viewBox="0 0 24 24" width="15" height="15" stroke="currentColor" stroke-width="2" fill="none">
          <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
        </svg>
      </button>
    </div>
  </div>
</header>

<style>
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 2rem;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-color);
    position: sticky;
    top: 0;
    z-index: 50;
    gap: 1.5rem;
    flex-wrap: wrap;
    box-shadow: var(--shadow-sm);
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 0.85rem;
  }

  .brand-icon {
    width: 40px;
    height: 40px;
    background: var(--accent-blue-light);
    color: var(--accent-blue);
    border: 1px solid #bfdbfe;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-md);
  }

  .titles h1 {
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.02em;
  }

  .title-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }

  .badge {
    font-size: 0.68rem;
    font-family: var(--font-mono);
    padding: 0.12rem 0.45rem;
    border-radius: var(--radius-sm);
    font-weight: 600;
  }

  .edge-badge {
    background: var(--accent-green-light);
    color: var(--accent-green);
    border: 1px solid #a7f3d0;
  }

  .subtitle {
    font-size: 0.78rem;
    color: var(--text-muted);
  }

  .controls {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .filter-group {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    background: var(--bg-primary);
    padding: 0.35rem 0.65rem;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-color);
    font-size: 0.8rem;
  }

  .filter-group label {
    color: var(--text-muted);
    font-weight: 500;
  }

  .filter-group select, .filter-group input {
    background: transparent;
    color: var(--text-primary);
    border: none;
    outline: none;
    font-size: 0.8rem;
  }

  .filter-group input {
    width: 90px;
  }

  .filter-group select option {
    background: #ffffff;
    color: var(--text-primary);
  }

  .status-indicator {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background: var(--bg-primary);
    padding: 0.35rem 0.75rem;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-color);
    font-size: 0.8rem;
  }

  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent-red);
    transition: background 0.2s ease;
  }

  .status-dot.connected {
    background: var(--accent-green);
  }

  .status-text {
    font-weight: 500;
    color: var(--text-secondary);
  }

  .timestamp {
    color: var(--text-muted);
    font-family: var(--font-mono);
    font-size: 0.75rem;
    margin-left: 0.2rem;
  }

  .settings-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.35rem 0.75rem;
    font-size: 0.78rem;
    font-weight: 600;
    background: #ffffff;
    color: var(--text-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    transition: all 0.15s ease;
  }

  .settings-btn:hover {
    color: var(--text-primary);
    border-color: #cbd5e1;
  }

  .settings-btn.active {
    background: var(--accent-blue-light);
    color: var(--accent-blue);
    border-color: #bfdbfe;
  }

  .refresh-controls {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .auto-refresh-toggle {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.75rem;
    color: var(--text-secondary);
    cursor: pointer;
    user-select: none;
  }

  .auto-refresh-toggle input {
    accent-color: var(--accent-blue);
    cursor: pointer;
  }

  .refresh-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    background: #ffffff;
    color: var(--text-secondary);
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-color);
    transition: all 0.15s ease;
  }

  .refresh-btn:hover {
    color: var(--accent-blue);
    border-color: #bfdbfe;
    background: var(--accent-blue-light);
  }

  .spinning svg {
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    100% { transform: rotate(360deg); }
  }
</style>
