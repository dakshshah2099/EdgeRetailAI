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
    fetchSystemZones,
    fetchSKUCatalog,
    checkHealth,
    resetTelemetry,
    resolveAllAlerts,
    resolveAlert,
    connectTelemetryWebSocket,
  } from "./lib/api.js";

  // App State
  let isConnected = $state(false);
  let isWsConnected = $state(false);
  let liveDwellPoints = $state([]);
  let isRefreshing = $state(false);
  let lastUpdated = $state(new Date());
  let autoRefresh = $state(true);
  let refreshIntervalSec = $state(3);
  let isSidebarCollapsed = $state(false);
  let isMobileSidebarOpen = $state(false);

  // Settings & System Env
  let envVariables = $state({});
  let systemZones = $state([]);
  let skuCatalog = $state([]);

  // Filters
  let selectedTimeRange = $state("all");
  let selectedZone = $state("");
  let selectedPlanogramShelf = $state("");
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

    const targetPlanoShelf =
      selectedPlanogramShelf ||
      (shelfZones.length > 0 ? shelfZones[0].zone_id : "zone_shelf_beverages");

    try {
      const [healthy, footfall, queue, stock, alerts, heatmap, sysEnv, sku, plano, staff, zonesRes, catalogRes] = await Promise.allSettled([
        checkHealth({ signal: ac.signal }),
        fetchKPIFootfall({ ...params, group_by: groupBy }, { signal: ac.signal }),
        fetchKPIQueue(params, { signal: ac.signal }),
        fetchKPIStock(params, { signal: ac.signal }),
        fetchAlerts({ status: alertFilter }, { signal: ac.signal }),
        fetchHeatmap(params, { signal: ac.signal }),
        fetchSystemEnv({ signal: ac.signal }),
        fetchKPISKU(params, { signal: ac.signal }),
        fetchPlanogramCompliance(targetPlanoShelf, { signal: ac.signal }),
        fetchKPIStaff(params, { signal: ac.signal }),
        fetchSystemZones({ signal: ac.signal }),
        fetchSKUCatalog({}, { signal: ac.signal }),
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
      if (zonesRes.status === "fulfilled" && Array.isArray(zonesRes.value)) {
        systemZones = zonesRes.value;
        if (!selectedPlanogramShelf && zonesRes.value.some((z) => z.zone_type === "shelf")) {
          const firstShelf = zonesRes.value.find((z) => z.zone_type === "shelf");
          if (firstShelf) selectedPlanogramShelf = firstShelf.zone_id;
        }
      }
      if (catalogRes.status === "fulfilled" && Array.isArray(catalogRes.value)) {
        skuCatalog = catalogRes.value;
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

  // Initial mount lifecycle & real-time WebSocket connection
  $effect(() => {
    setupRouting();
    loadAllData();

    const wsClient = connectTelemetryWebSocket(
      (msg) => {
        if (!msg || !msg.type) return;
        if (msg.type === "dwell_points") {
          liveDwellPoints = msg.points || [];
        } else if (msg.type === "occupancy") {
          const occ = typeof msg.net_occupancy === "number" ? msg.net_occupancy : 0;
          if (footfallData) {
            footfallData = {
              ...footfallData,
              net_occupancy: occ,
            };
          } else {
            footfallData = {
              total_enters: 0,
              total_exits: 0,
              net_occupancy: occ,
            };
          }
          lastUpdated = new Date();
        } else if (msg.type === "footfall") {
          const deltaEnters = msg.new_enters ?? msg.total_enters ?? 0;
          const deltaExits = msg.new_exits ?? msg.total_exits ?? 0;
          const currentEnters = (footfallData?.total_enters || 0) + deltaEnters;
          const currentExits = (footfallData?.total_exits || 0) + deltaExits;
          const liveOcc = msg.net_occupancy !== undefined 
            ? msg.net_occupancy 
            : (msg.data?.net_occupancy !== undefined ? msg.data.net_occupancy : Math.max(0, currentEnters - currentExits));
          footfallData = {
            ...(footfallData || {}),
            total_enters: currentEnters,
            total_exits: currentExits,
            net_occupancy: liveOcc,
          };
          lastUpdated = new Date();
        } else if (msg.type === "queue") {
          const qData = Array.isArray(msg.data)
            ? msg.data
            : (Array.isArray(msg.counters) ? msg.counters : []);
          if (qData.length > 0) {
            queueData = qData;
          }
          lastUpdated = new Date();
        } else if (msg.type === "stock_update") {
          if (Array.isArray(msg.data)) {
            stockData = msg.data;
          } else {
            fetchKPIStock({ zone_id: selectedZone || null }).then((res) => { stockData = res; }).catch(() => {});
            fetchKPISKU({ zone_id: selectedZone || null }).then((res) => { skuReport = res; }).catch(() => {});
          }
          fetchAlerts({ status: alertFilter }).then((res) => { alertsData = res; }).catch(() => {});
          lastUpdated = new Date();
        } else if (msg.type === "alerts_update") {
          fetchAlerts({ status: alertFilter }).then((res) => { alertsData = res; }).catch(() => {});
          lastUpdated = new Date();
        }
      },
      ({ connected }) => {
        isWsConnected = connected;
        if (connected) isConnected = true;
      }
    );

    return () => {
      page.stop();
      wsClient.disconnect();
      if (activeAbortController) activeAbortController.abort();
    };
  });

  // Fallback polling loop when auto-refresh is active and WebSocket is disconnected
  $effect(() => {
    if (!autoRefresh || refreshIntervalSec <= 0) return;
    const timer = setInterval(() => {
      if (!isWsConnected) {
        loadAllData();
      }
    }, Math.max(1, refreshIntervalSec) * 1000);

    return () => clearInterval(timer);
  });

  // Derived KPI metrics
  let shelfZones = $derived(systemZones.filter((z) => z.zone_type === "shelf"));
  let occupancy = $derived(footfallData ? footfallData.net_occupancy : 0);
  let totalEnters = $derived(footfallData ? footfallData.total_enters : 0);
  let totalExits = $derived(footfallData ? footfallData.total_exits : 0);
  let maxQueueLength = $derived(queueData.length ? Math.max(...queueData.map((q) => q.queue_length)) : 0);
  let lowStockShelves = $derived(stockData.filter((s) => s.status === "empty" || s.status === "low").length);
  let openAlertsCount = $derived(alertsData.filter((a) => !a.resolved_at).length);
</script>

<svelte:head>
  <title>{routeMeta[activeTab]?.title || "Dashboard"} — Dukaanlytics</title>
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
      {isWsConnected}
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
              <LiveCameraFeed {isConnected} {occupancy} />
            </div>
            <div class="lg:col-span-1 flex flex-col gap-2.5">
              <!-- Camera Page Subpanel Switcher -->
              <div class="flex items-center bg-white border border-slate-200 rounded-md p-1 shadow-xs">
                <button
                  type="button"
                  class={[
                    "flex-1 py-1 px-2 text-xs font-mono rounded cursor-pointer transition-colors",
                    cameraSideTab === "alerts"
                      ? "bg-sky-50 text-sky-900 border border-sky-300 font-semibold"
                      : "text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-transparent"
                  ]}
                  onclick={() => cameraSideTab = "alerts"}
                >
                  INCIDENTS ({openAlertsCount})
                </button>
                <button
                  type="button"
                  class={[
                    "flex-1 py-1 px-2 text-xs font-mono rounded cursor-pointer transition-colors",
                    cameraSideTab === "telemetry"
                      ? "bg-sky-50 text-sky-900 border border-sky-300 font-semibold"
                      : "text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-transparent"
                  ]}
                  onclick={() => cameraSideTab = "telemetry"}
                >
                  STREAM TELEMETRY
                </button>
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
                      <span class="text-sky-800 font-semibold">YOLOv26n Acceleration</span>
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
                      <span class="text-slate-500">Data Policy</span>
                      <span class="text-emerald-700 font-semibold">In-Memory / Ephemeral</span>
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
              <HeatmapCanvas {heatmapData} isLoading={isRefreshing} livePoints={liveDwellPoints} />
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
          <StockInventory stockEvents={stockData} {skuReport} {skuCatalog} />
        {:else if activeTab === "planogram"}
          <PlanogramCompliance 
            {planogramData} 
            {shelfZones}
            selectedShelfId={selectedPlanogramShelf}
            isLoading={isRefreshing} 
            onSelectShelf={(sId) => {
              selectedPlanogramShelf = sId;
              loadAllData();
            }}
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
