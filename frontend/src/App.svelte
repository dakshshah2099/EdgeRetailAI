<script>
  import { onMount, onDestroy } from "svelte";
  import page from "page";
  import Header from "./components/Header.svelte";
  import Sidebar from "./components/Sidebar.svelte";
  import KPICard from "./components/KPICard.svelte";
  import HeatmapCanvas from "./components/HeatmapCanvas.svelte";
  import LiveCameraFeed from "./components/LiveCameraFeed.svelte";
  import AlertsFeed from "./components/AlertsFeed.svelte";
  import FootfallChart from "./components/FootfallChart.svelte";
  import QueueMonitor from "./components/QueueMonitor.svelte";
  import StockInventory from "./components/StockInventory.svelte";
  import DebugControlPanel from "./components/DebugControlPanel.svelte";
  import {
    fetchKPIFootfall,
    fetchKPIQueue,
    fetchKPIStock,
    fetchAlerts,
    fetchHeatmap,
    fetchSystemEnv,
    checkHealth,
  } from "./lib/api.js";

  // App State
  let isConnected = false;
  let isRefreshing = false;
  let lastUpdated = new Date();
  let autoRefresh = true;
  let refreshIntervalSec = 3;
  let refreshTimer = null;
  let isSidebarCollapsed = false;
  let isMobileSidebarOpen = false;

  // Settings & System Env
  let envVariables = {};

  // Filters
  let selectedTimeRange = "all";
  let selectedZone = "";
  let groupBy = "hour";
  let alertFilter = "open";

  // Camera Feed Page Subpanel Tab
  let cameraSideTab = "alerts"; // 'alerts' | 'telemetry'

  // Data Store
  let footfallData = null;
  let queueData = [];
  let stockData = [];
  let alertsData = [];
  let heatmapData = null;

  // Active Route Identifier
  let activeTab = "camera"; // 'camera' | 'heatmap' | 'footfall' | 'queues' | 'stock' | 'alerts' | 'settings'

  const validRoutes = ["camera", "heatmap", "footfall", "queues", "stock", "alerts", "settings"];

  const routeMeta = {
    camera: {
      title: "Live Camera Stream",
      category: "Live Vision",
      desc: "Real-time RTSP ingest, YOLOv26n inference & interactive ROI calibration",
    },
    heatmap: {
      title: "Customer Dwell Heatmap",
      category: "Live Vision",
      desc: "Spatial dwell distribution and customer attention density mapping",
    },
    footfall: {
      title: "Footfall Traffic Trends",
      category: "Store Intelligence",
      desc: "Store entry/exit flow, net occupancy, and peak-hour accumulation",
    },
    queues: {
      title: "Checkout Queue Intelligence",
      category: "Store Intelligence",
      desc: "Register line length, customer dwell time, and congestion monitoring",
    },
    stock: {
      title: "Shelf Inventory & Depletions",
      category: "Store Intelligence",
      desc: "Visual shelf out-of-stock monitoring and low stock replenishment triggers",
    },
    alerts: {
      title: "Operations Incident Log",
      category: "Operations",
      desc: "Real-time alert triage, status filtering, and incident resolution",
    },
    settings: {
      title: "Edge Node Configuration",
      category: "Operations",
      desc: "Runtime inference parameters, video sources, and camera hyperparameters",
    },
  };

  $: if (typeof document !== "undefined" && routeMeta[activeTab]) {
    document.title = `${routeMeta[activeTab].title} — EdgeRetail AI`;
  }

  function setupRouting() {
    page("/", () => {
      activeTab = "camera";
    });

    validRoutes.forEach((route) => {
      page(`/${route}`, () => {
        activeTab = route;
      });
    });

    page("*", () => {
      activeTab = "camera";
    });

    page.start({ hashbang: true });
  }

  function navigateTo(tab) {
    isMobileSidebarOpen = false;
    page(`/${tab}`);
  }

  function getSinceISO(range) {
    const now = new Date();
    if (range === "1h") return new Date(now.getTime() - 3600 * 1000).toISOString();
    if (range === "6h") return new Date(now.getTime() - 6 * 3600 * 1000).toISOString();
    if (range === "24h") return new Date(now.getTime() - 24 * 3600 * 1000).toISOString();
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

      isConnected = healthy.status === "fulfilled" && healthy.value;
      if (footfall.status === "fulfilled") footfallData = footfall.value;
      if (queue.status === "fulfilled") queueData = queue.value;
      if (stock.status === "fulfilled") stockData = stock.value;
      if (alerts.status === "fulfilled") alertsData = alerts.value;
      if (heatmap.status === "fulfilled") heatmapData = heatmap.value;
      if (sysEnv.status === "fulfilled") {
        envVariables = sysEnv.value.variables;
      }

      lastUpdated = new Date();
    } catch (err) {
      console.error("Failed to load dashboard data:", err);
      isConnected = false;
    } finally {
      isRefreshing = false;
    }
  }

  function handleToggleSidebar() {
    isSidebarCollapsed = !isSidebarCollapsed;
  }

  function handleEnvSaved(res) {
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
    setupRouting();
    loadAllData();
    setupPolling();
  });

  onDestroy(() => {
    page.stop();
    if (refreshTimer) clearInterval(refreshTimer);
  });

  // Derived KPI metrics
  $: occupancy = footfallData ? footfallData.net_occupancy : 0;
  $: totalEnters = footfallData ? footfallData.total_enters : 0;
  $: totalExits = footfallData ? footfallData.total_exits : 0;
  $: maxQueueLength = queueData.length ? Math.max(...queueData.map((q) => q.queue_length)) : 0;
  $: lowStockShelves = stockData.filter((s) => s.status === "empty" || s.status === "low").length;
  $: openAlertsCount = alertsData.filter((a) => !a.resolved_at).length;
</script>

<div class="h-screen w-screen overflow-hidden bg-slate-50 text-slate-900 flex font-sans">
  <!-- Left Persistent Navigation Sidebar / Mobile Off-Canvas Drawer -->
  <Sidebar
    {activeTab}
    queueCount={queueData.length}
    stockCount={stockData.length}
    alertsCount={openAlertsCount}
    isCollapsed={isSidebarCollapsed}
    isMobileOpen={isMobileSidebarOpen}
    onSelectTab={navigateTo}
    onToggleCollapse={handleToggleSidebar}
    onCloseMobile={() => isMobileSidebarOpen = false}
  />

  <!-- Main Viewport Area -->
  <div class="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
    <!-- Top Operational Header -->
    <Header
      {isConnected}
      {lastUpdated}
      {isRefreshing}
      bind:autoRefresh
      bind:refreshInterval={refreshIntervalSec}
      bind:selectedTimeRange
      bind:selectedZone
      onRefresh={loadAllData}
      onToggleMobileMenu={() => isMobileSidebarOpen = !isMobileSidebarOpen}
    />

    <main class="flex-1 p-2.5 sm:p-4 max-w-[1720px] w-full mx-auto flex flex-col gap-2.5 sm:gap-3 overflow-y-auto">
      <!-- Telemetry Readout Grid -->
      <section class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 sm:gap-2.5">
        <KPICard
          title="Occupancy"
          value={occupancy.toString()}
          subtitle={`IN: ${totalEnters} • OUT: ${totalExits}`}
          icon="occupancy"
          tag="REALTIME"
          status={occupancy > 30 ? "warning" : "normal"}
        />

        <KPICard
          title="Footfall"
          value={totalEnters.toString()}
          subtitle="Cumulative window enters"
          icon="footfall"
          tag="CUMULATIVE"
          status="normal"
        />

        <KPICard
          title="Max Queue"
          value={`${maxQueueLength}`}
          subtitle={`${queueData.length} counters monitored`}
          icon="queue"
          tag={maxQueueLength >= 4 ? "CONGESTED" : "OPTIMAL"}
          status={maxQueueLength >= 4 ? "danger" : "success"}
        />

        <KPICard
          title="Depletions"
          value={`${lowStockShelves}`}
          subtitle={`Across ${stockData.length} active shelves`}
          icon="stock"
          tag={lowStockShelves > 0 ? "ATTENTION" : "STOCKED"}
          status={lowStockShelves > 0 ? "warning" : "success"}
        />

        <div class="col-span-2 sm:col-span-1">
          <KPICard
            title="Alert Stack"
            value={openAlertsCount.toString()}
            subtitle="Unresolved triage items"
            icon="alerts"
            tag={openAlertsCount > 0 ? "ALERTING" : "SECURE"}
            status={openAlertsCount > 0 ? "danger" : "success"}
          />
        </div>
      </section>

      <!-- Dedicated Route Context Banner -->
      <div class="flex items-center justify-between flex-wrap gap-2 px-1 pt-0.5">
        <div class="flex items-center gap-2 text-xs font-mono">
          <span class="text-slate-500 uppercase">{routeMeta[activeTab]?.category || "Vision"}</span>
          <span class="text-slate-300">/</span>
          <h1 class="text-sm font-semibold text-slate-900">{routeMeta[activeTab]?.title || "Dashboard"}</h1>
        </div>
        <p class="text-xs text-slate-500 font-sans hidden sm:block">
          {routeMeta[activeTab]?.desc || ""}
        </p>
      </div>

      <!-- Primary Stage Viewport: Dedicated Routed Views -->
      <section class="flex-1 min-h-[460px]">
        {#if activeTab === "camera"}
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-3 h-full">
            <div class="lg:col-span-2">
              <LiveCameraFeed {isConnected} />
            </div>
            <div class="lg:col-span-1 flex flex-col gap-2.5">
              <!-- Camera Page Subpanel Switcher -->
              <div class="flex items-center bg-white border border-slate-200 rounded-md p-1 shadow-xs">
                {#if cameraSideTab === "alerts"}
                  <button
                    type="button"
                    class="flex-1 py-1 px-2 text-xs font-mono rounded bg-sky-50 text-sky-900 border border-sky-300 font-semibold cursor-pointer transition-colors"
                    on:click={() => cameraSideTab = "alerts"}
                  >
                    INCIDENTS ({openAlertsCount})
                  </button>
                  <button
                    type="button"
                    class="flex-1 py-1 px-2 text-xs font-mono rounded text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-transparent cursor-pointer transition-colors"
                    on:click={() => cameraSideTab = "telemetry"}
                  >
                    STREAM TELEMETRY
                  </button>
                {:else}
                  <button
                    type="button"
                    class="flex-1 py-1 px-2 text-xs font-mono rounded text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-transparent cursor-pointer transition-colors"
                    on:click={() => cameraSideTab = "alerts"}
                  >
                    INCIDENTS ({openAlertsCount})
                  </button>
                  <button
                    type="button"
                    class="flex-1 py-1 px-2 text-xs font-mono rounded bg-sky-50 text-sky-900 border border-sky-300 font-semibold cursor-pointer transition-colors"
                    on:click={() => cameraSideTab = "telemetry"}
                  >
                    STREAM TELEMETRY
                  </button>
                {/if}
              </div>

              {#if cameraSideTab === "alerts"}
                <AlertsFeed 
                  alerts={alertsData} 
                  activeFilter={alertFilter} 
                  onFilterChange={(st) => { alertFilter = st; loadAllData(); }} 
                />
              {:else}
                <!-- Stream Diagnostics & Telemetry Card -->
                <div class="bg-white border border-slate-200 rounded-md shadow-xs p-4 flex flex-col gap-3 font-mono text-xs">
                  <div class="flex items-center justify-between border-b border-slate-100 pb-2.5">
                    <span class="font-semibold text-slate-900 uppercase">Camera Ingest Telemetry</span>
                    <span class="px-2 py-0.5 rounded border text-xs {isConnected ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-rose-50 text-rose-800 border-rose-200'}">
                      {isConnected ? 'FEED ACTIVE' : 'FEED OFFLINE'}
                    </span>
                  </div>

                  <div class="space-y-2.5">
                    <div class="flex items-center justify-between py-1 border-b border-slate-100">
                      <span class="text-slate-500">Video Ingest Source</span>
                      <span class="text-slate-800 font-semibold truncate max-w-[180px]" title={envVariables.VIDEO_SOURCE || "0 (USB Camera / RTSP)"}>
                        {envVariables.VIDEO_SOURCE || "0 (Default Camera)"}
                      </span>
                    </div>

                    <div class="flex items-center justify-between py-1 border-b border-slate-100">
                      <span class="text-slate-500">Inference Backend</span>
                      <span class="text-sky-800 font-semibold">ONNX Runtime (YOLOv26n)</span>
                    </div>

                    <div class="flex items-center justify-between py-1 border-b border-slate-100">
                      <span class="text-slate-500">Target Resolution</span>
                      <span class="text-slate-800">640 × 640 Letterbox</span>
                    </div>

                    <div class="flex items-center justify-between py-1 border-b border-slate-100">
                      <span class="text-slate-500">Detection Confidence</span>
                      <span class="text-slate-800 font-semibold">{envVariables.YOLO_CONF_THRESHOLD || "0.40"}</span>
                    </div>

                    <div class="flex items-center justify-between py-1 border-b border-slate-100">
                      <span class="text-slate-500">NMS IoU Threshold</span>
                      <span class="text-slate-800 font-semibold">{envVariables.YOLO_IOU_THRESHOLD || "0.45"}</span>
                    </div>

                    <div class="flex items-center justify-between py-1 border-b border-slate-100">
                      <span class="text-slate-500">Queue Congestion Level</span>
                      <span class="text-amber-800 font-semibold">≥ {envVariables.QUEUE_CONGESTION_THRESHOLD || "4"} persons</span>
                    </div>

                    <div class="flex items-center justify-between py-1 border-b border-slate-100">
                      <span class="text-slate-500">Depletion Warning Level</span>
                      <span class="text-rose-800 font-semibold">≤ {envVariables.STOCK_LOW_THRESHOLD || "3"} units</span>
                    </div>

                    <div class="flex items-center justify-between py-1">
                      <span class="text-slate-500">Privacy & PII Policy</span>
                      <span class="text-emerald-700 font-semibold">In-Memory / Zero Disk</span>
                    </div>
                  </div>

                  <div class="pt-2 border-t border-slate-100 flex items-center justify-between">
                    <span class="text-slate-400 text-xs">Need to change source or thresholds?</span>
                    <button
                      type="button"
                      class="px-2.5 py-1 rounded bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 cursor-pointer transition-colors"
                      on:click={() => navigateTo("settings")}
                    >
                      Open Config →
                    </button>
                  </div>
                </div>
              {/if}
            </div>
          </div>
        {:else if activeTab === "heatmap"}
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-3 h-full">
            <div class="lg:col-span-2">
              <HeatmapCanvas {heatmapData} isLoading={isRefreshing} />
            </div>
            <div class="lg:col-span-1">
              <AlertsFeed 
                alerts={alertsData} 
                activeFilter={alertFilter} 
                onFilterChange={(st) => { alertFilter = st; loadAllData(); }} 
              />
            </div>
          </div>
        {:else if activeTab === "footfall"}
          <FootfallChart 
            {footfallData} 
            {groupBy} 
            onGroupByChange={(gb) => { groupBy = gb; loadAllData(); }} 
          />
        {:else if activeTab === "queues"}
          <QueueMonitor queueEvents={queueData} congestionThreshold={4} />
        {:else if activeTab === "stock"}
          <StockInventory stockEvents={stockData} />
        {:else if activeTab === "alerts"}
          <AlertsFeed 
            alerts={alertsData} 
            activeFilter={alertFilter} 
            onFilterChange={(st) => { alertFilter = st; loadAllData(); }} 
          />
        {:else if activeTab === "settings"}
          <DebugControlPanel 
            {envVariables} 
            onSave={handleEnvSaved} 
          />
        {/if}
      </section>
    </main>
  </div>
</div>
