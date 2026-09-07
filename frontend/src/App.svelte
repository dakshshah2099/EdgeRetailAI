<script>
  import { onMount, onDestroy } from 'svelte';
  import Header from './components/Header.svelte';
  import KPICard from './components/KPICard.svelte';
  import HeatmapCanvas from './components/HeatmapCanvas.svelte';
  import LiveCameraFeed from './components/LiveCameraFeed.svelte';
  import AlertsFeed from './components/AlertsFeed.svelte';
  import FootfallChart from './components/FootfallChart.svelte';
  import QueueMonitor from './components/QueueMonitor.svelte';
  import StockInventory from './components/StockInventory.svelte';
  import DebugControlPanel from './components/DebugControlPanel.svelte';
  import {
    fetchKPIFootfall,
    fetchKPIQueue,
    fetchKPIStock,
    fetchAlerts,
    fetchHeatmap,
    fetchSystemEnv,
    toggleDebugMode,
    checkHealth,
  } from './lib/api.js';

  // App State
  let isConnected = false;
  let isRefreshing = false;
  let lastUpdated = new Date();
  let autoRefresh = true;
  let refreshIntervalSec = 3;
  let refreshTimer = null;

  // Debug & System Env
  let debugMode = false;
  let envVariables = {};

  // Filters
  let selectedTimeRange = 'all';
  let selectedZone = '';
  let groupBy = 'hour';
  let alertFilter = 'open';

  // Data Store
  let footfallData = null;
  let queueData = [];
  let stockData = [];
  let alertsData = [];
  let heatmapData = null;

  // Active Main Tab
  let activeTab = 'camera'; // 'camera' | 'heatmap' | 'footfall' | 'queues' | 'stock' | 'alerts' | 'debug'

  function getSinceISO(range) {
    const now = new Date();
    if (range === '1h') return new Date(now.getTime() - 3600 * 1000).toISOString();
    if (range === '6h') return new Date(now.getTime() - 6 * 3600 * 1000).toISOString();
    if (range === '24h') return new Date(now.getTime() - 24 * 3600 * 1000).toISOString();
    return null;
  }

  async function loadAllData() {
    isRefreshing = true;
    const since = getSinceISO(selectedTimeRange);
    const params = {
      zone_id: selectedZone || null,
      since: since || null,
    };

    try {
      const [healthy, footfall, queue, stock, alerts, heatmap, sysEnv] = await Promise.allSettled([
        checkHealth(),
        fetchKPIFootfall({ ...params, group_by: groupBy }),
        fetchKPIQueue(),
        fetchKPIStock(),
        fetchAlerts({ status: alertFilter }),
        fetchHeatmap(params),
        fetchSystemEnv(),
      ]);

      isConnected = healthy.status === 'fulfilled' && healthy.value;
      if (footfall.status === 'fulfilled') footfallData = footfall.value;
      if (queue.status === 'fulfilled') queueData = queue.value;
      if (stock.status === 'fulfilled') stockData = stock.value;
      if (alerts.status === 'fulfilled') alertsData = alerts.value;
      if (heatmap.status === 'fulfilled') heatmapData = heatmap.value;
      if (sysEnv.status === 'fulfilled') {
        debugMode = sysEnv.value.debug_mode;
        envVariables = sysEnv.value.variables;
      }

      lastUpdated = new Date();
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
      isConnected = false;
    } finally {
      isRefreshing = false;
    }
  }

  async function handleToggleDebug() {
    try {
      const res = await toggleDebugMode();
      debugMode = res.debug_mode;
      envVariables = res.variables;
      if (debugMode) {
        activeTab = 'debug';
      } else if (activeTab === 'debug') {
        activeTab = 'camera';
      }
    } catch (err) {
      console.error('Failed to toggle debug mode:', err);
    }
  }

  function handleEnvSaved(res) {
    debugMode = res.debug_mode;
    envVariables = res.variables;
    loadAllData();
  }

  function setupPolling() {
    if (refreshTimer) clearInterval(refreshTimer);
    if (autoRefresh && refreshIntervalSec > 0) {
      refreshTimer = setInterval(() => {
        loadAllData();
      }, refreshIntervalSec * 1000);
    }
  }

  $: autoRefresh, refreshIntervalSec, setupPolling();

  onMount(() => {
    loadAllData();
    setupPolling();
  });

  onDestroy(() => {
    if (refreshTimer) clearInterval(refreshTimer);
  });

  // Derived KPI metrics
  $: occupancy = footfallData ? footfallData.net_occupancy : 0;
  $: totalEnters = footfallData ? footfallData.total_enters : 0;
  $: totalExits = footfallData ? footfallData.total_exits : 0;
  $: maxQueueLength = queueData.length ? Math.max(...queueData.map((q) => q.queue_length)) : 0;
  $: lowStockShelves = stockData.filter((s) => s.status === 'empty' || s.status === 'low').length;
  $: openAlertsCount = alertsData.filter((a) => !a.resolved_at).length;
</script>

<Header
  {isConnected}
  {lastUpdated}
  {isRefreshing}
  {debugMode}
  bind:autoRefresh
  bind:refreshInterval={refreshIntervalSec}
  bind:selectedTimeRange
  bind:selectedZone
  onRefresh={loadAllData}
  onToggleDebug={handleToggleDebug}
/>

<main class="dashboard-main">
  <!-- Top KPI Metric Summary Cards -->
  <section class="kpi-grid">
    <KPICard
      title="Current Occupancy"
      value={occupancy.toString()}
      subtitle={`Enters: ${totalEnters} • Exits: ${totalExits}`}
      icon="occupancy"
      tag="Live"
      status={occupancy > 30 ? 'warning' : 'normal'}
    />

    <KPICard
      title="Total Footfall"
      value={totalEnters.toString()}
      subtitle="Cumulative recorded enters"
      icon="footfall"
      tag="Cumulative"
      status="normal"
    />

    <KPICard
      title="Peak Queue Length"
      value={`${maxQueueLength} persons`}
      subtitle={`${queueData.length} checkout counters active`}
      icon="queue"
      tag={maxQueueLength >= 4 ? 'Congested' : 'Optimal'}
      status={maxQueueLength >= 4 ? 'danger' : 'success'}
    />

    <KPICard
      title="Stock Depletions"
      value={`${lowStockShelves} low/empty`}
      subtitle={`Across ${stockData.length} monitored shelves`}
      icon="stock"
      tag={lowStockShelves > 0 ? 'Action Needed' : 'Optimal'}
      status={lowStockShelves > 0 ? 'warning' : 'success'}
    />

    <KPICard
      title="Active Alerts"
      value={openAlertsCount.toString()}
      subtitle="Unresolved system notices"
      icon="alerts"
      tag={openAlertsCount > 0 ? 'Active' : 'Clear'}
      status={openAlertsCount > 0 ? 'danger' : 'success'}
    />
  </section>

  <!-- Navigation View Tabs -->
  <div class="view-tabs">
    <button class="view-tab" class:active={activeTab === 'camera'} on:click={() => activeTab = 'camera'}>
      Live Camera Feed
    </button>
    <button class="view-tab" class:active={activeTab === 'heatmap'} on:click={() => activeTab = 'heatmap'}>
      Traffic Heatmap
    </button>
    <button class="view-tab" class:active={activeTab === 'footfall'} on:click={() => activeTab = 'footfall'}>
      Footfall Trends
    </button>
    <button class="view-tab" class:active={activeTab === 'queues'} on:click={() => activeTab = 'queues'}>
      Checkout Queues ({queueData.length})
    </button>
    <button class="view-tab" class:active={activeTab === 'stock'} on:click={() => activeTab = 'stock'}>
      Shelf Stock ({stockData.length})
    </button>
    <button class="view-tab" class:active={activeTab === 'alerts'} on:click={() => activeTab = 'alerts'}>
      Alert Log ({alertsData.length})
    </button>
    {#if debugMode}
      <button class="view-tab debug-tab" class:active={activeTab === 'debug'} on:click={() => activeTab = 'debug'}>
        System .env Debug
      </button>
    {/if}
  </div>

  <!-- Primary Analytics Content Area -->
  <section class="content-view">
    {#if activeTab === 'camera'}
      <div class="grid-2col">
        <LiveCameraFeed {isConnected} {debugMode} />
        <AlertsFeed 
          alerts={alertsData} 
          activeFilter={alertFilter} 
          onFilterChange={(st) => { alertFilter = st; loadAllData(); }} 
        />
      </div>
    {:else if activeTab === 'heatmap'}
      <div class="grid-2col">
        <HeatmapCanvas {heatmapData} isLoading={isRefreshing} />
        <AlertsFeed 
          alerts={alertsData} 
          activeFilter={alertFilter} 
          onFilterChange={(st) => { alertFilter = st; loadAllData(); }} 
        />
      </div>
    {:else if activeTab === 'footfall'}
      <FootfallChart 
        {footfallData} 
        {groupBy} 
        onGroupByChange={(gb) => { groupBy = gb; loadAllData(); }} 
      />
    {:else if activeTab === 'queues'}
      <QueueMonitor queueEvents={queueData} congestionThreshold={4} />
    {:else if activeTab === 'stock'}
      <StockInventory stockEvents={stockData} />
    {:else if activeTab === 'alerts'}
      <AlertsFeed 
        alerts={alertsData} 
        activeFilter={alertFilter} 
        onFilterChange={(st) => { alertFilter = st; loadAllData(); }} 
      />
    {:else if activeTab === 'debug'}
      <DebugControlPanel 
        {debugMode} 
        {envVariables} 
        onSave={handleEnvSaved} 
      />
    {/if}
  </section>
</main>

<style>
  .dashboard-main {
    flex: 1;
    padding: 1.5rem 2rem 3rem;
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    max-width: 1600px;
    width: 100%;
    margin: 0 auto;
  }

  .kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1rem;
  }

  .view-tabs {
    display: flex;
    gap: 0.35rem;
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 0.5rem;
    overflow-x: auto;
  }

  .view-tab {
    padding: 0.5rem 1rem;
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--text-secondary);
    border-radius: var(--radius-sm);
    transition: all 0.15s ease;
    white-space: nowrap;
    border: 1px solid transparent;
  }

  .view-tab:hover {
    color: var(--text-primary);
    background: #ffffff;
  }

  .view-tab.active {
    background: var(--accent-blue);
    color: #ffffff;
    box-shadow: var(--shadow-sm);
    font-weight: 600;
  }

  .view-tab.debug-tab {
    color: var(--accent-purple);
    border: 1px dashed #ddd6fe;
    margin-left: auto;
    background: var(--accent-purple-light);
  }

  .view-tab.debug-tab.active {
    background: var(--accent-purple);
    color: #ffffff;
    border-color: var(--accent-purple);
  }

  .content-view {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .grid-2col {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
  }

  @media (max-width: 1024px) {
    .grid-2col {
      grid-template-columns: 1fr;
    }
  }
</style>
