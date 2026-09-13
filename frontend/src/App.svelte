<script>
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
  import PlanogramCompliance from "./components/PlanogramCompliance.svelte";
  import StaffEfficiency from "./components/StaffEfficiency.svelte";
  import ReportsManager from "./components/ReportsManager.svelte";
  import {
    fetchKPIFootfall,
    fetchKPIQueue,
    fetchKPIStock,
    fetchKPISKU,
    fetchPlanogramCompliance,
    fetchKPIStaff,
    fetchAlerts,
    fetchHeatmap,
    fetchSystemEnv,
    checkHealth,
    resetTelemetry,
    resolveAllAlerts,
    resolveAlert,
  } from "./lib/api.js";

  // App State
  let isConnected = $state(false);
  let isRefreshing = $state(false);
  let lastUpdated = $state(new Date());
  let autoRefresh = $state(true);
  let refreshIntervalSec = $state(3);
  let isSidebarCollapsed = $state(false);
  let isMobileSidebarOpen = $state(false);

  // Settings & System Env
  let envVariables = $state({});

  // Filters
  let selectedTimeRange = $state("all");
  let selectedZone = $state("");
  let groupBy = $state("hour");
  let alertFilter = $state("open");

  // Camera Feed Page Subpanel Tab
  let cameraSideTab = $state("alerts"); // 'alerts' | 'telemetry'

  // Large API Data Store using $state.raw for maximum performance without proxy overhead
  let footfallData = $state.raw(null);
  let queueData = $state.raw([]);
  let stockData = $state.raw([]);
  let skuReport = $state.raw(null);
  let planogramData = $state.raw(null);
  let staffData = $state.raw(null);
  let alertsData = $state.raw([]);
  let heatmapData = $state.raw(null);

  // Active Route Identifier
  let activeTab = $state("camera"); // 'camera' | 'heatmap' | 'footfall' | 'queues' | 'stock' | 'planogram' | 'staff' | 'reports' | 'alerts' | 'settings'

  const validRoutes = [
    "camera",
    "heatmap",
    "footfall",
    "queues",
    "stock",
    "planogram",
    "staff",
    "reports",
    "alerts",
    "settings",
  ];

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
    planogram: {
      title: "Planogram-Lite Compliance",
      category: "Store Intelligence",
      desc: "Shelf facing grid subdivision, expected layout compliance, and empty facing detection",
    },
    staff: {
      title: "Staff Efficiency Analytics",
      category: "Store Intelligence",
      desc: "Counter utilization, recommendation follow rates, and operational alert response speed",
    },
    reports: {
      title: "Automated Daily Reports",
      category: "Operations",
      desc: "On-demand shift and daily analytics compilation with CSV & PDF report downloads",
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

  let activeAbortController = null;

  async function loadAllData() {
    if (activeAbortController) {
      activeAbortController.abort();
    }
    const ac = new AbortController();
    activeAbortController = ac;
    isRefreshing = true;

    const since = getSinceISO(selectedTimeRange);
    const params = {
      zone_id: selectedZone || null,
      since: since || null,
    };

    try {
      const [healthy, footfall, queue, stock, alerts, heatmap, sysEnv, sku, plano, staff] = await Promise.allSettled([
        checkHealth({ signal: ac.signal }),
        fetchKPIFootfall({ ...params, group_by: groupBy }, { signal: ac.signal }),
        fetchKPIQueue(params, { signal: ac.signal }),
        fetchKPIStock(params, { signal: ac.signal }),
        fetchAlerts({ status: alertFilter }, { signal: ac.signal }),
        fetchHeatmap(params, { signal: ac.signal }),
        fetchSystemEnv({ signal: ac.signal }),
        fetchKPISKU(params, { signal: ac.signal }),
        fetchPlanogramCompliance("zone_shelf_beverages", { signal: ac.signal }),
        fetchKPIStaff(params, { signal: ac.signal }),
      ]);

      if (ac.signal.aborted) return;

      isConnected = healthy.status === "fulfilled" && healthy.value;
      if (footfall.status === "fulfilled") footfallData = footfall.value;
      if (queue.status === "fulfilled") queueData = queue.value;
      if (stock.status === "fulfilled") stockData = stock.value;
      if (alerts.status === "fulfilled") alertsData = alerts.value;
      if (heatmap.status === "fulfilled") heatmapData = heatmap.value;
      if (sku.status === "fulfilled") skuReport = sku.value;
      if (plano.status === "fulfilled") planogramData = plano.value;
      if (staff.status === "fulfilled") staffData = staff.value;
      if (sysEnv.status === "fulfilled") {
        envVariables = sysEnv.value.variables;
      }

      lastUpdated = new Date();
    } catch (err) {
      if (ac.signal.aborted) return;
      console.error("Failed to load dashboard data:", err);
      isConnected = false;
    } finally {
      if (!ac.signal.aborted) {
        isRefreshing = false;
      }
    }
  }

  function handleToggleSidebar() {
    isSidebarCollapsed = !isSidebarCollapsed;
  }

  function handleEnvSaved(res) {
    envVariables = res.variables;
    loadAllData();
  }

  async function handleResolveAlert(alertId) {
    try {
      await resolveAlert(alertId);
      await loadAllData();
    } catch (err) {
      console.error("Failed to resolve alert:", err);
    }
  }

  async function handleResolveAllAlerts() {
    try {
      await resolveAllAlerts();
      await loadAllData();
    } catch (err) {
      console.error("Failed to resolve all alerts:", err);
    }
  }

  // Reactive polling interval with automatic cleanup
  $effect(() => {
    if (autoRefresh && refreshIntervalSec > 0) {
      const timer = setInterval(() => {
        loadAllData();
      }, refreshIntervalSec * 1000);
      return () => clearInterval(timer);
    }
  });

  // Initial mount lifecycle
  $effect(() => {
    setupRouting();
    loadAllData();
    return () => {
      page.stop();
      if (activeAbortController) activeAbortController.abort();
    };
  });

  // Derived KPI metrics
  let occupancy = $derived(footfallData ? footfallData.net_occupancy : 0);
  let totalEnters = $derived(footfallData ? footfallData.total_enters : 0);
  let totalExits = $derived(footfallData ? footfallData.total_exits : 0);
  let maxQueueLength = $derived(queueData.length ? Math.max(...queueData.map((q) => q.queue_length)) : 0);
  let lowStockShelves = $derived(stockData.filter((s) => s.status === "empty" || s.status === "low").length);
  let openAlertsCount = $derived(alertsData.filter((a) => !a.resolved_at).length);
</script>

<svelte:head>
  <title>{routeMeta[activeTab]?.title || "Dashboard"} — EdgeRetail AI</title>
</svelte:head>

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
                    onclick={() => cameraSideTab = "alerts"}
                  >
                    INCIDENTS ({openAlertsCount})
                  </button>
                  <button
                    type="button"
                    class="flex-1 py-1 px-2 text-xs font-mono rounded text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-transparent cursor-pointer transition-colors"
                    onclick={() => cameraSideTab = "telemetry"}
                  >
                    STREAM TELEMETRY
                  </button>
                {:else}
                  <button
                    type="button"
                    class="flex-1 py-1 px-2 text-xs font-mono rounded text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-transparent cursor-pointer transition-colors"
                    onclick={() => cameraSideTab = "alerts"}
                  >
                    INCIDENTS ({openAlertsCount})
                  </button>
                  <button
                    type="button"
                    class="flex-1 py-1 px-2 text-xs font-mono rounded bg-sky-50 text-sky-900 border border-sky-300 font-semibold cursor-pointer transition-colors"
                    onclick={() => cameraSideTab = "telemetry"}
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
                  onResolveAlert={handleResolveAlert}
                  onResolveAllAlerts={handleResolveAllAlerts}
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
                      onclick={() => navigateTo("settings")}
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
                onResolveAlert={handleResolveAlert}
                onResolveAllAlerts={handleResolveAllAlerts}
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
          <StockInventory stockEvents={stockData} {skuReport} />
        {:else if activeTab === "planogram"}
          <PlanogramCompliance 
            {planogramData} 
            zoneId={selectedZone || "zone_shelf_beverages"} 
            isLoading={isRefreshing} 
            onRefresh={loadAllData} 
          />
        {:else if activeTab === "staff"}
          <StaffEfficiency 
            {staffData} 
            isLoading={isRefreshing} 
            onRefresh={loadAllData} 
          />
        {:else if activeTab === "reports"}
          <ReportsManager />
        {:else if activeTab === "alerts"}
          <AlertsFeed 
            alerts={alertsData} 
            activeFilter={alertFilter} 
            onFilterChange={(st) => { alertFilter = st; loadAllData(); }} 
            onResolveAlert={handleResolveAlert}
            onResolveAllAlerts={handleResolveAllAlerts}
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
