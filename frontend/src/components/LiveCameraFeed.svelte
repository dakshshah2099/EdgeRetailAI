<script>
  import { onMount, onDestroy } from "svelte";
  import { fetchSystemZones, updateSystemZones } from "../lib/api.js";

  export let isConnected = true;

  let overlayZones = true;
  let overlayDetections = true;
  let targetFps = typeof window !== "undefined"
    ? parseInt(localStorage.getItem("preferred_stream_fps") || "15", 10) || 15
    : 15;

  $: if (typeof window !== "undefined" && targetFps) {
    localStorage.setItem("preferred_stream_fps", targetFps.toString());
  }

  let streamTimestamp = Date.now();
  let isStreamLoading = true;
  let isStreamError = false;
  let videoContainer;
  let isFullscreen = false;

  // Visual Zone Calibration
  let isEditingZones = false;
  let zones = [];
  let selectedZoneIdx = 0;
  let activeDragHandle = null; // { zoneIdx, ptIdx }
  let isSavingZones = false;
  let zoneStatusMsg = "";
  let isZoneError = false;

  // Viewport dimensions & cursor tracker
  let viewWidth = 640;
  let viewHeight = 480;
  let cursorX = 0;
  let cursorY = 0;

  // CCTV Live UTC Watermark
  let camClock = "";
  let clockTimer = null;

  function updateClock() {
    const now = new Date();
    camClock = now.toISOString().replace("T", " ").slice(0, 19) + " UTC";
  }

  $: streamUrl = `/video/stream?overlay_zones=${!isEditingZones && overlayZones}&overlay_detections=${overlayDetections}&fps=${targetFps}&t=${streamTimestamp}`;

  const zoneColorMap = {
    entry_exit: {
      stroke: "#059669",
      fill: "rgba(5, 150, 105, 0.20)",
    },
    shelf: {
      stroke: "#0284c7",
      fill: "rgba(2, 132, 199, 0.20)",
    },
    checkout: {
      stroke: "#d97706",
      fill: "rgba(217, 119, 6, 0.20)",
    },
    product_display: {
      stroke: "#e11d48",
      fill: "rgba(225, 29, 72, 0.20)",
    },
  };

  function getZoneTheme(zoneType) {
    return zoneColorMap[zoneType] || zoneColorMap.shelf;
  }

  async function loadZones() {
    try {
      zones = await fetchSystemZones();
    } catch (err) {
      console.error("Failed to load zones:", err);
    }
  }

  function refreshStream() {
    isStreamLoading = true;
    isStreamError = false;
    streamTimestamp = Date.now();
  }

  function handleImageLoad(e) {
    isStreamLoading = false;
    isStreamError = false;
    if (e.target && e.target.naturalWidth) {
      viewWidth = e.target.naturalWidth;
      viewHeight = e.target.naturalHeight;
    }
  }

  function handleImageError() {
    isStreamLoading = false;
    isStreamError = true;
  }

  function toggleFullscreen() {
    if (!videoContainer) return;
    if (!document.fullscreenElement) {
      videoContainer.requestFullscreen().catch((err) => {
        console.error("Fullscreen request failed:", err);
      });
      isFullscreen = true;
    } else {
      document.exitFullscreen();
      isFullscreen = false;
    }
  }

  function takeSnapshot() {
    const link = document.createElement("a");
    link.href = `/video/snapshot?overlay_zones=${overlayZones}&overlay_detections=${overlayDetections}&t=${Date.now()}`;
    link.download = `retail_snapshot_${new Date().toISOString().replace(/[:.]/g, "-")}.jpg`;
    link.target = "_blank";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  function startZoneEdit() {
    isEditingZones = true;
    zoneStatusMsg = "";
    loadZones();
  }

  function cancelZoneEdit() {
    isEditingZones = false;
    loadZones();
  }

  async function saveZones() {
    isSavingZones = true;
    zoneStatusMsg = "";
    isZoneError = false;
    try {
      zones = await updateSystemZones(zones);
      zoneStatusMsg = "✓ Zone configuration saved to config.yaml successfully.";
      isZoneError = false;
      refreshStream();
    } catch (err) {
      zoneStatusMsg = `Error: ${err.message}`;
      isZoneError = true;
    } finally {
      isSavingZones = false;
    }
  }

  function addZone() {
    const newId = `zone_${Date.now().toString().slice(-4)}`;
    const newZone = {
      zone_id: newId,
      zone_type: "shelf",
      label: `Shelf ${zones.length + 1}`,
      polygon: [
        [100, 100],
        [300, 100],
        [300, 300],
        [100, 300],
      ],
    };
    zones = [...zones, newZone];
    selectedZoneIdx = zones.length - 1;
  }

  function removeZone(idx) {
    zones = zones.filter((_, i) => i !== idx);
    if (selectedZoneIdx >= zones.length) {
      selectedZoneIdx = Math.max(0, zones.length - 1);
    }
  }

  function handleSvgMouseDown(zoneIdx, ptIdx, e) {
    e.stopPropagation();
    selectedZoneIdx = zoneIdx;
    activeDragHandle = { zoneIdx, ptIdx };
  }

  function handleSvgMouseMove(e) {
    const svgRect = e.currentTarget.getBoundingClientRect();
    const scaleX = viewWidth / svgRect.width;
    const scaleY = viewHeight / svgRect.height;

    cursorX = Math.round(Math.max(0, Math.min(viewWidth, (e.clientX - svgRect.left) * scaleX)));
    cursorY = Math.round(Math.max(0, Math.min(viewHeight, (e.clientY - svgRect.top) * scaleY)));

    if (!activeDragHandle) return;

    const { zoneIdx, ptIdx } = activeDragHandle;
    const nextZones = JSON.parse(JSON.stringify(zones));
    nextZones[zoneIdx].polygon[ptIdx] = [cursorX, cursorY];
    zones = nextZones;
  }

  function handleSvgMouseUp() {
    activeDragHandle = null;
  }

  onMount(() => {
    loadZones();
    updateClock();
    clockTimer = setInterval(updateClock, 1000);

    const handleFsChange = () => {
      isFullscreen = !!document.fullscreenElement;
    };
    document.addEventListener("fullscreenchange", handleFsChange);
    return () => {
      document.removeEventListener("fullscreenchange", handleFsChange);
    };
  });

  onDestroy(() => {
    if (clockTimer) clearInterval(clockTimer);
  });
</script>

<div 
  class="bg-white border border-slate-200 rounded-md shadow-xs flex flex-col gap-2.5 sm:gap-3 p-3 sm:p-4 transition-all duration-150 {isFullscreen ? 'fixed inset-0 z-50 bg-slate-950 p-4 sm:p-6 rounded-none border-none' : ''} {isEditingZones ? 'ring-2 ring-amber-500/50' : ''}" 
  bind:this={videoContainer}
>
  <!-- Stream Header Toolbar -->
  <div class="flex items-center justify-between flex-wrap gap-2 sm:gap-2.5 pb-2 sm:pb-2.5 border-b border-slate-100">
    <div class="flex items-center gap-2 sm:gap-2.5 flex-wrap">
      <div class="flex items-center gap-2">
        <span class="w-2.5 h-2.5 rounded-full {isConnected && !isStreamError ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}"></span>
        <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-900">Live Camera Stream</h2>
      </div>
      <span class="px-2 py-0.5 text-xs font-mono font-semibold uppercase rounded border {isConnected && !isStreamError ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-rose-50 text-rose-800 border-rose-200'}">
        {isConnected && !isStreamError ? 'LIVE' : 'STANDBY'}
      </span>
      <span class="px-2 py-0.5 text-xs font-mono bg-sky-50 text-sky-800 border border-sky-200 rounded hidden sm:inline">
        YOLOv26n Active
      </span>
      {#if isEditingZones}
        <span class="px-2 py-0.5 text-xs font-mono font-semibold bg-amber-50 text-amber-800 border border-amber-300 rounded animate-pulse">
          CALIBRATION MODE
        </span>
      {/if}
    </div>

    <!-- Quick Overlays & Actions Controls -->
    <div class="flex items-center gap-2 flex-wrap">
      <!-- Overlay Toggle Buttons -->
      {#if overlayZones}
        <button 
          type="button"
          class="flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono rounded border border-sky-300 bg-sky-50 text-sky-800 font-semibold cursor-pointer transition-colors"
          on:click={() => { overlayZones = false; refreshStream(); }}
          title="Toggle ROI zone overlays on video stream"
        >
          <span class="w-2 h-2 rounded-full bg-sky-500"></span>
          <span>ROI ZONES</span>
        </button>
      {:else}
        <button 
          type="button"
          class="flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono rounded border border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100 cursor-pointer transition-colors"
          on:click={() => { overlayZones = true; refreshStream(); }}
          title="Toggle ROI zone overlays on video stream"
        >
          <span class="w-2 h-2 rounded-full bg-slate-400"></span>
          <span>ROI ZONES</span>
        </button>
      {/if}

      {#if overlayDetections}
        <button 
          type="button"
          class="flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono rounded border border-emerald-300 bg-emerald-50 text-emerald-800 font-semibold cursor-pointer transition-colors"
          on:click={() => { overlayDetections = false; refreshStream(); }}
          title="Toggle YOLO bounding box overlays on video stream"
        >
          <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
          <span>YOLO BOXES</span>
        </button>
      {:else}
        <button 
          type="button"
          class="flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono rounded border border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100 cursor-pointer transition-colors"
          on:click={() => { overlayDetections = true; refreshStream(); }}
          title="Toggle YOLO bounding box overlays on video stream"
        >
          <span class="w-2 h-2 rounded-full bg-slate-400"></span>
          <span>YOLO BOXES</span>
        </button>
      {/if}

      <!-- Zone Calibration Toggle -->
      {#if !isEditingZones}
        <button 
          type="button" 
          class="flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono bg-slate-50 text-slate-700 border border-slate-200 rounded hover:bg-slate-100 transition-colors cursor-pointer"
          on:click={startZoneEdit}
          title="Calibrate detection polygons interactively"
        >
          <svg class="w-3.5 h-3.5 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="22" y1="12" x2="18" y2="12"/>
            <line x1="6" y1="12" x2="2" y2="12"/>
            <line x1="12" y1="6" x2="12" y2="2"/>
            <line x1="12" y1="22" x2="12" y2="18"/>
          </svg>
          <span>CALIBRATE</span>
        </button>
      {:else}
        <button 
          type="button" 
          class="px-2.5 py-1 text-xs font-mono bg-sky-50 text-sky-800 border border-sky-200 rounded hover:bg-sky-100 font-semibold cursor-pointer"
          on:click={addZone}
        >
          + NEW ZONE
        </button>
        <button 
          type="button" 
          class="px-2.5 py-1 text-xs font-mono bg-slate-100 text-slate-700 border border-slate-200 rounded hover:bg-slate-200 cursor-pointer"
          on:click={cancelZoneEdit}
        >
          CANCEL
        </button>
        <button 
          type="button" 
          class="px-2.5 py-1 text-xs font-mono bg-sky-600 text-white rounded hover:bg-sky-700 font-semibold disabled:opacity-50 cursor-pointer"
          on:click={saveZones} 
          disabled={isSavingZones}
        >
          {isSavingZones ? 'SAVING...' : 'SAVE ZONES'}
        </button>
      {/if}

      <!-- FPS Selector -->
      <div class="flex items-center bg-slate-50 border border-slate-200 rounded px-2 py-0.5 text-xs font-mono text-slate-700">
        <span class="text-slate-500 mr-1">FPS:</span>
        <input 
          type="number" 
          min="1" 
          max="60" 
          class="w-10 bg-transparent text-slate-900 font-semibold focus:outline-none"
          bind:value={targetFps} 
          on:change={refreshStream}
        />
      </div>

      <!-- Action Buttons -->
      <button 
        type="button" 
        class="p-1.5 rounded text-slate-600 hover:text-sky-700 hover:bg-slate-100 border border-slate-200 transition-colors cursor-pointer"
        on:click={takeSnapshot} 
        title="Capture JPEG Snapshot"
      >
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2v26a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
          <circle cx="12" cy="13" r="4"/>
        </svg>
      </button>

      <button 
        type="button" 
        class="p-1.5 rounded text-slate-600 hover:text-sky-700 hover:bg-slate-100 border border-slate-200 transition-colors cursor-pointer"
        on:click={refreshStream} 
        title="Reconnect Video Stream"
      >
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="23 4 23 10 17 10"/>
          <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
        </svg>
      </button>

      <button 
        type="button" 
        class="p-1.5 rounded text-slate-600 hover:text-sky-700 hover:bg-slate-100 border border-slate-200 transition-colors cursor-pointer"
        on:click={toggleFullscreen} 
        title="Toggle Fullscreen"
      >
        {#if isFullscreen}
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="4 14 10 14 10 20"/>
            <polyline points="20 10 14 10 14 4"/>
            <line x1="14" y1="10" x2="21" y2="3"/>
            <line x1="3" y1="21" x2="10" y2="14"/>
          </svg>
        {:else}
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="15 3 21 3 21 9"/>
            <polyline points="9 21 3 21 3 15"/>
            <line x1="21" y1="3" x2="14" y2="10"/>
            <line x1="3" y1="21" x2="10" y2="14"/>
          </svg>
        {/if}
      </button>
    </div>
  </div>

  <!-- Status Notification -->
  {#if zoneStatusMsg}
    <div class="px-3 py-1.5 text-xs font-mono rounded border {isZoneError ? 'bg-rose-50 text-rose-800 border-rose-200' : 'bg-emerald-50 text-emerald-800 border-emerald-200'}">
      {zoneStatusMsg}
    </div>
  {/if}

  <!-- Stream Player & Overlays Viewport -->
  <div class="relative w-full aspect-video bg-slate-950 rounded-md overflow-hidden flex items-center justify-center border border-slate-800">
    <img 
      src={streamUrl} 
      alt="Edge AI Live Camera Feed" 
      class="w-full h-full object-contain select-none"
      on:load={handleImageLoad}
      on:error={handleImageError}
    />

    <!-- Top Watermark & CCTV Timecode Overlay -->
    <div class="absolute top-2 sm:top-2.5 left-2 sm:left-2.5 right-2 sm:right-2.5 flex items-center justify-between gap-1 pointer-events-none text-xs font-mono z-10">
      <div class="flex items-center gap-1.5 sm:gap-2 bg-slate-950/80 backdrop-blur-xs border border-slate-800 text-slate-200 px-2 py-0.5 rounded shadow-sm">
        <span class="w-2 h-2 rounded-full {isConnected && !isStreamError ? 'bg-emerald-400 animate-pulse' : 'bg-rose-500'}"></span>
        <span class="text-slate-400">CAM_01</span>
        <span class="text-slate-600">|</span>
        <span class="text-slate-200">{camClock}</span>
      </div>

      {#if isEditingZones}
        <div class="flex items-center gap-1.5 sm:gap-2 bg-amber-950/80 backdrop-blur-xs border border-amber-600/50 text-amber-200 px-2 sm:px-2.5 py-0.5 rounded shadow-sm">
          <span class="w-2 h-2 rounded-full bg-amber-400 animate-ping"></span>
          <span class="hidden sm:inline">CALIBRATING</span>
          <span class="text-amber-400 font-bold">X:{cursorX} Y:{cursorY}</span>
        </div>
      {/if}
    </div>

    <!-- Interactive SVG ROI polygon editor in Calibration mode -->
    {#if isEditingZones}
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <svg 
        class="absolute inset-0 w-full h-full cursor-crosshair select-none z-20" 
        viewBox="0 0 {viewWidth} {viewHeight}"
        on:mousemove={handleSvgMouseMove}
        on:mouseup={handleSvgMouseUp}
        on:mouseleave={handleSvgMouseUp}
      >
        {#each zones as zone, zIdx}
          {@const isSel = zIdx === selectedZoneIdx}
          {@const theme = getZoneTheme(zone.zone_type)}
          {@const ptsStr = zone.polygon.map((p) => p.join(',')).join(' ')}
          <polygon
            points={ptsStr}
            stroke={theme.stroke}
            stroke-width={isSel ? '2.5' : '1.5'}
            stroke-dasharray={isSel ? '4 2' : 'none'}
            fill={theme.fill}
            class="transition-all cursor-pointer"
            on:mousedown={() => selectedZoneIdx = zIdx}
          />
          <text
            x={zone.polygon[0][0]}
            y={Math.max(18, zone.polygon[0][1] - 8)}
            class="fill-white font-mono text-xs font-bold drop-shadow"
          >
            {zone.label} ({zone.zone_type})
          </text>

          {#if isSel}
            {#each zone.polygon as pt, ptIdx}
              <circle
                cx={pt[0]}
                cy={pt[1]}
                r="6"
                fill={theme.stroke}
                class="stroke-2 stroke-white cursor-grab hover:scale-125 transition-transform"
                on:mousedown={(e) => handleSvgMouseDown(zIdx, ptIdx, e)}
              />
            {/each}
          {/if}
        {/each}
      </svg>
    {/if}

    <!-- Loading State Overlay -->
    {#if isStreamLoading}
      <div class="absolute inset-0 bg-slate-950/85 backdrop-blur-xs flex flex-col items-center justify-center gap-2 text-sky-400 font-mono text-xs z-30">
        <span class="w-3 h-3 rounded-full bg-sky-400 animate-ping"></span>
        <span>INITIALIZING LIVE CAMERA STREAM...</span>
      </div>
    {/if}

    <!-- Stream Error Fallback -->
    {#if isStreamError}
      <div class="absolute inset-0 bg-slate-950 flex flex-col items-center justify-center gap-2 text-rose-400 font-mono text-xs p-4 text-center z-30">
        <svg class="w-8 h-8 text-rose-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <span class="font-semibold">RTSP STREAM DISCONNECTED / OFFLINE</span>
        <p class="text-slate-400 text-xs max-w-sm">Ensure local camera RTSP feed is active or update VIDEO_SOURCE in Configuration.</p>
        <button 
          type="button" 
          class="mt-2 px-3 py-1 bg-slate-800 text-slate-200 border border-slate-700 rounded hover:bg-slate-700 cursor-pointer"
          on:click={refreshStream}
        >
          RETRY CONNECTION
        </button>
      </div>
    {/if}

    <!-- Live Stream HUD -->
    <div class="absolute bottom-2 sm:bottom-2.5 left-2 sm:left-2.5 right-2 sm:right-2.5 flex items-center justify-between gap-1 pointer-events-none text-xs font-mono z-10">
      <div class="flex items-center gap-1 sm:gap-1.5 bg-slate-900/90 backdrop-blur-xs border border-slate-700 text-slate-200 px-2 sm:px-2.5 py-0.5 sm:py-1 rounded shadow-md truncate">
        <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0"></span>
        <span>{targetFps} FPS</span>
        <span class="text-slate-500">|</span>
        <span class="text-slate-300">{viewWidth}×{viewHeight}</span>
        <span class="text-slate-500 hidden sm:inline">|</span>
        <span class="text-sky-400 hidden sm:inline">YOLOv26n ONNX-RT</span>
      </div>

      <div class="flex items-center gap-1 sm:gap-1.5 bg-slate-900/90 backdrop-blur-xs border border-slate-700 text-slate-300 px-2 sm:px-2.5 py-0.5 sm:py-1 rounded shadow-md shrink-0">
        {#if overlayZones}
          <span class="text-sky-400 hidden md:inline">ZONES: ON</span>
        {/if}
        {#if overlayDetections}
          <span class="text-emerald-400 hidden md:inline">YOLO: ON</span>
        {/if}
        <span class="text-slate-500 hidden md:inline">|</span>
        <span class="text-emerald-400 font-semibold">ZERO PII</span>
      </div>
    </div>
  </div>

  <!-- Calibration Mode Editor Form -->
  {#if isEditingZones}
    <div class="bg-slate-50 border border-slate-200 rounded p-2.5 sm:p-3 flex items-center justify-between flex-wrap gap-2 text-xs font-mono">
      {#if zones.length > 0 && zones[selectedZoneIdx]}
        <div class="flex items-center gap-2 flex-wrap w-full sm:w-auto">
          <div class="flex items-center gap-1">
            <label for="zone-select" class="text-slate-600 font-semibold">Zone:</label>
            <select id="zone-select" bind:value={selectedZoneIdx} class="bg-white border border-slate-200 rounded px-2 py-1 text-slate-900">
              {#each zones as z, i}
                <option value={i}>{z.label || `Zone ${i + 1}`} ({z.zone_type})</option>
              {/each}
            </select>
          </div>

          <div class="flex items-center gap-1">
            <label for="zone-label-input" class="text-slate-600 font-semibold">Label:</label>
            <input 
              id="zone-label-input"
              type="text" 
              bind:value={zones[selectedZoneIdx].label} 
              class="bg-white border border-slate-200 rounded px-2 py-1 text-slate-900 w-24 sm:w-28"
            />
          </div>

          <div class="flex items-center gap-1">
            <label for="zone-type-select" class="text-slate-600 font-semibold">Type:</label>
            <select id="zone-type-select" bind:value={zones[selectedZoneIdx].zone_type} class="bg-white border border-slate-200 rounded px-2 py-1 text-slate-900">
              <option value="entry_exit">Entry / Exit</option>
              <option value="shelf">Product Shelf</option>
              <option value="checkout">Checkout Queue</option>
              <option value="product_display">Product Display</option>
            </select>
          </div>

          <div class="flex items-center gap-1">
            <label for="zone-id-input" class="text-slate-600 font-semibold">ID:</label>
            <input 
              id="zone-id-input"
              type="text" 
              bind:value={zones[selectedZoneIdx].zone_id} 
              class="bg-white border border-slate-200 rounded px-2 py-1 text-slate-900 w-20 sm:w-24"
            />
          </div>
        </div>

        <div class="flex items-center gap-2 w-full sm:w-auto justify-end">
          <button type="button" class="px-2.5 py-1 bg-white border border-slate-200 text-slate-700 rounded hover:bg-slate-100 cursor-pointer" on:click={addZone}>
            + Add Zone
          </button>
          <button type="button" class="px-2.5 py-1 bg-rose-50 border border-rose-200 text-rose-800 rounded hover:bg-rose-100 font-semibold cursor-pointer" on:click={() => removeZone(selectedZoneIdx)}>
            Delete
          </button>
        </div>
      {:else}
        <div class="flex items-center justify-between w-full">
          <span class="text-slate-500">No detection zones configured.</span>
          <button type="button" class="px-2.5 py-1 bg-sky-600 text-white rounded hover:bg-sky-700 cursor-pointer" on:click={addZone}>
            + Create Zone
          </button>
        </div>
      {/if}
    </div>
  {/if}

  <!-- Footer Legend -->
  <div class="flex items-center justify-between flex-wrap gap-2 text-xs font-mono text-slate-500 pt-1">
    <div class="flex items-center gap-3 flex-wrap">
      <span class="flex items-center gap-1.5"><span class="w-2 h-2 rounded-full bg-emerald-500"></span> Entry/Exit</span>
      <span class="flex items-center gap-1.5"><span class="w-2 h-2 rounded-full bg-sky-500"></span> Shelf ROI</span>
      <span class="flex items-center gap-1.5"><span class="w-2 h-2 rounded-full bg-amber-500"></span> Queue Lane</span>
      <span class="flex items-center gap-1.5"><span class="w-2 h-2 rounded-full bg-rose-500"></span> Display</span>
    </div>
    <span>Purely in-memory edge inference • Zero raw frame retention</span>
  </div>
</div>
