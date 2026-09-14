<script>
  import { onMount } from "svelte";
  import { fetchCentralStores } from "../lib/api.js";

  let {
    activeTab = "camera",
    queueCount = 0,
    stockCount = 0,
    alertsCount = 0,
    isCollapsed = false,
    isMobileOpen = false,
    onSelectTab = () => {},
    onToggleCollapse = () => {},
    onCloseMobile = () => {}
  } = $props();

  let configuredStoreCount = $state(3);

  onMount(async () => {
    const data = await fetchCentralStores();
    if (Array.isArray(data) && data.length > 0) {
      configuredStoreCount = data.length;
    }
  });

  function handleTabClick(tab) {
    onSelectTab(tab);
    onCloseMobile();
  }
</script>

<!-- Reusable Svelte 5 Snippet for Navigation Links -->
{#snippet navItem(tab, label, iconSvg, count = 0, badgeTheme = "sky")}
  {@const isSelected = activeTab === tab}
  {@const isAlertIcon = badgeTheme === "rose" && count > 0}
  <div class="relative group">
    <a
      href="#!/{tab}"
      class={[
        "w-full flex items-center gap-2.5 py-1.5 rounded-md text-xs transition-all cursor-pointer select-none",
        isCollapsed ? "justify-center px-0" : "justify-start px-2.5",
        isSelected
          ? "font-semibold bg-sky-50 text-sky-900 border border-sky-300 shadow-xs"
          : "font-medium bg-transparent text-slate-700 hover:bg-slate-100 hover:text-slate-900 border border-transparent"
      ]}
      onclick={(e) => { e.preventDefault(); handleTabClick(tab); }}
    >
      <svg
        class={[
          "w-4 h-4 shrink-0 transition-colors",
          isSelected ? (isAlertIcon ? "text-rose-600" : "text-sky-800") : (isAlertIcon ? "text-rose-600" : "text-slate-500")
        ]}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
      >
        {@render iconSvg()}
      </svg>

      {#if !isCollapsed}
        <span class="flex-1 text-left truncate">{label}</span>
        {#if count > 0}
          <span class={[
            "px-1.5 py-0.5 text-xs font-mono rounded border",
            badgeTheme === "rose" ? "bg-rose-100 text-rose-800 font-semibold border-rose-200" :
            badgeTheme === "amber" ? "bg-amber-100 text-amber-800 border-amber-200" :
            isSelected ? "bg-sky-100 text-sky-900 border-sky-200" : "bg-slate-100 text-slate-800 border-slate-200"
          ]}>
            {count}
          </span>
        {/if}
      {:else if count > 0}
        <span class={[
          "absolute top-1.5 right-2 w-2 h-2 rounded-full",
          badgeTheme === "rose" ? "bg-rose-600" : badgeTheme === "amber" ? "bg-amber-500" : "bg-sky-600"
        ]}></span>
      {/if}
    </a>

    {#if isCollapsed}
      <div class="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-3 hidden group-hover:flex items-center gap-1.5 px-2.5 py-1 bg-slate-900 text-slate-100 text-xs font-sans rounded shadow-xl whitespace-nowrap z-50 border border-slate-700">
        <span>{label}</span>
        {#if count > 0}
          <span class={[
            "font-mono",
            badgeTheme === "rose" ? "text-rose-400 font-semibold" : badgeTheme === "amber" ? "text-amber-400" : "text-sky-400"
          ]}>
            ({count})
          </span>
        {/if}
      </div>
    {/if}
  </div>
{/snippet}

<!-- Mobile Overlay Backdrop -->
{#if isMobileOpen}
  <button
    type="button"
    aria-label="Close navigation sidebar"
    class="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-40 md:hidden cursor-pointer"
    onclick={onCloseMobile}
  ></button>
{/if}

<aside
  class={[
    "bg-white border-r border-slate-200 flex flex-col justify-between h-full select-none z-50 fixed inset-y-0 left-0 max-w-[80vw] transition-transform duration-200 ease-out shadow-xl md:shadow-none md:static md:translate-x-0 shrink-0",
    isMobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0",
    isCollapsed ? "md:w-14 md:overflow-visible" : "md:w-52 w-64"
  ]}
>
  <!-- Brand Area -->
  <div class="p-2.5 border-b border-slate-200 flex items-center justify-between gap-2 shrink-0">
    <div class={["flex items-center gap-2 overflow-hidden", isCollapsed && "md:justify-center md:w-full"]}>
      <div class="w-7 h-7 rounded-md bg-sky-600 flex items-center justify-center text-white shrink-0 shadow-xs">
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
        </svg>
      </div>
      <div class={["overflow-hidden", isCollapsed ? "md:hidden" : "block"]}>
        <div class="font-bold text-xs tracking-tight text-slate-900 leading-tight">Dukaanlytics</div>
      </div>
    </div>

    <!-- Mobile Close Button -->
    <button
      type="button"
      class="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100 md:hidden cursor-pointer"
      onclick={onCloseMobile}
      title="Close navigation"
    >
      <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="18" y1="6" x2="6" y2="18"/>
        <line x1="6" y1="6" x2="18" y2="18"/>
      </svg>
    </button>
  </div>

  <!-- Navigation Menu Groups -->
  <nav class={["flex-1 p-1.5 space-y-3", isCollapsed ? "overflow-visible" : "overflow-y-auto"]}>
    <!-- Group 1: Live Vision & Spatial -->
    <div>
      {#if !isCollapsed}
        <div class="px-2 pb-1 text-xs font-mono font-semibold uppercase tracking-wider text-slate-400">
          Live Vision
        </div>
      {/if}
      <div class="space-y-0.5">
        {#snippet cameraIcon()}
          <polygon points="23 7 16 12 23 17 23 7"/>
          <rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
        {/snippet}
        {@render navItem("camera", "Camera Feed", cameraIcon)}

        {#snippet heatmapIcon()}
          <rect x="3" y="3" width="18" height="18" rx="2"/>
          <path d="M3 9h18M9 21V9"/>
        {/snippet}
        {@render navItem("heatmap", "Dwell Heatmap", heatmapIcon)}
      </div>
    </div>

    <!-- Group 2: Store Intelligence & Telemetry -->
    <div>
      {#if !isCollapsed}
        <div class="px-2 pb-1 text-xs font-mono font-semibold uppercase tracking-wider text-slate-400">
          Store Intelligence
        </div>
      {/if}
      <div class="space-y-0.5">
        {#snippet footfallIcon()}
          <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
          <polyline points="17 6 23 6 23 12"/>
        {/snippet}
        {@render navItem("footfall", "Footfall Trends", footfallIcon)}

        {#snippet queueIcon()}
          <rect x="1" y="4" width="22" height="16" rx="2" ry="2"/>
          <line x1="1" y1="10" x2="23" y2="10"/>
        {/snippet}
        {@render navItem("queues", "Checkout Queues", queueIcon, queueCount, "sky")}

        {#snippet stockIcon()}
          <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
          <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
          <line x1="12" y1="22.08" x2="12" y2="12"/>
        {/snippet}
        {@render navItem("stock", "Shelf Inventory", stockIcon, stockCount, "amber")}

        {#snippet planoIcon()}
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
          <line x1="3" y1="9" x2="21" y2="9"/>
          <line x1="9" y1="21" x2="9" y2="9"/>
        {/snippet}
        {@render navItem("planogram", "Planogram", planoIcon)}

        {#snippet staffIcon()}
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
          <circle cx="9" cy="7" r="4"/>
          <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
          <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
        {/snippet}
        {@render navItem("staff", "Staff Efficiency", staffIcon)}

        {#snippet reportsIcon()}
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
          <polyline points="10 9 9 9 8 9"/>
        {/snippet}
        {@render navItem("reports", "Daily Reports", reportsIcon)}
      </div>
    </div>

    <!-- Group 3: Operations & System -->
    <div>
      {#if !isCollapsed}
        <div class="px-2 pb-1 text-xs font-mono font-semibold uppercase tracking-wider text-slate-400">
          Operations
        </div>
      {/if}
      <div class="space-y-0.5">
        {#snippet alertsIcon()}
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
          <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
        {/snippet}
        {@render navItem("alerts", "Incident Log", alertsIcon, alertsCount, "rose")}

        {#snippet settingsIcon()}
          <circle cx="12" cy="12" r="3"/>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        {/snippet}
        {@render navItem("settings", "Configuration", settingsIcon)}

        <!-- Central Multi-Store Monitor External Link -->
        <div class="relative group">
          <a
            href="/central"
            target="_blank"
            rel="noopener noreferrer"
            class={[
              "w-full flex items-center gap-2.5 py-1.5 rounded-md text-xs font-medium bg-transparent text-slate-700 hover:bg-slate-100 hover:text-slate-900 border border-transparent transition-all cursor-pointer select-none",
              isCollapsed ? "justify-center px-0" : "justify-start px-2.5"
            ]}
            title="Open Central Multi-Store Operations Monitor"
          >
            <svg class="w-4 h-4 shrink-0 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
              <polyline points="9 22 9 12 15 12 15 22"/>
            </svg>
            {#if !isCollapsed}
              <span class="flex-1 text-left truncate">Multi-Store</span>
              <span class="text-2xs font-mono text-slate-400">{configuredStoreCount} {configuredStoreCount === 1 ? 'STORE' : 'STORES'}</span>
            {/if}
          </a>
          {#if isCollapsed}
            <div class="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-3 hidden group-hover:flex items-center px-2.5 py-1 bg-slate-900 text-slate-100 text-xs font-sans rounded shadow-xl whitespace-nowrap z-50 border border-slate-700">
              Multi-Store Monitor
            </div>
          {/if}
        </div>
      </div>
    </div>
  </nav>

  <!-- Sidebar Footer -->
  <div class="p-2 border-t border-slate-200 bg-slate-50/80 text-xs font-mono text-slate-500 flex flex-col gap-2 shrink-0">
    {#if !isCollapsed}
      <div class="space-y-1">
        <div class="flex items-center justify-between">
          <span class="text-slate-500">RUNTIME</span>
          <strong class="text-slate-800">ACTIVE</strong>
        </div>
        <div class="flex items-center justify-between">
          <span class="text-slate-500">STORAGE</span>
          <strong class="text-emerald-700 font-semibold">EPHEMERAL</strong>
        </div>
      </div>
    {:else}
      <div class="flex flex-col items-center justify-center gap-1 group relative cursor-pointer" title="Runtime: Active | Storage: Ephemeral">
        <span class="w-2 h-2 rounded-xs bg-slate-400"></span>
        <div class="pointer-events-none absolute left-full bottom-0 ml-3 hidden group-hover:flex flex-col gap-0.5 px-2.5 py-1 bg-slate-900 text-slate-100 text-xs font-mono rounded shadow-xl whitespace-nowrap z-50 border border-slate-700">
          <span>RUNTIME: ACTIVE</span>
          <span class="text-emerald-400 font-semibold">STORAGE: EPHEMERAL</span>
        </div>
      </div>
    {/if}

    <!-- Bottom Collapse Toggle Button -->
    <div class="relative group">
      <button
        type="button"
        class={[
          "w-full flex items-center rounded text-xs text-slate-600 hover:text-slate-900 hover:bg-slate-200/70 border border-slate-200 transition-colors cursor-pointer",
          isCollapsed ? "justify-center p-1.5" : "justify-between px-2 py-1"
        ]}
        onclick={onToggleCollapse}
        title={isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
      >
        {#if !isCollapsed}
          <span class="flex items-center gap-1.5">
            <svg class="w-3.5 h-3.5 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="15 18 9 12 15 6"/>
            </svg>
            <span class="font-mono font-medium">COLLAPSE</span>
          </span>
          <span class="text-slate-400 font-mono">«</span>
        {:else}
          <svg class="w-3.5 h-3.5 text-slate-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        {/if}
      </button>
      {#if isCollapsed}
        <div class="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-3 hidden group-hover:flex items-center px-2.5 py-1 bg-slate-900 text-slate-100 text-xs font-sans rounded shadow-xl whitespace-nowrap z-50 border border-slate-700">
          Expand Sidebar
        </div>
      {/if}
    </div>
  </div>
</aside>
