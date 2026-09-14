<script>
  import { 
    fetchSystemZones, 
    updateSystemZones, 
    fetchCameras, 
    registerCamera, 
    unregisterCamera 
  } from "../lib/api.js";

  let { isConnected = true } = $props();

  let cameras = $state([
    { camera_id: "cam_primary", label: "Primary (Overhead Entrance)", is_active: true }
  ]);

  let isAddCameraOpen = $state(false);
  let newCamId = $state("");
  let newCamSource = $state("");
  let newCamLabel = $state("");
  let newCamRole = $state("general");
  let isSubmittingCam = $state(false);
  let camErrorMsg = $state("");

  let overlayZones = $state(true);
  let overlayDetections = $state(true);
  let targetFps = $state(
    typeof window !== "undefined"
      ? parseInt(localStorage.getItem("preferred_stream_fps") || "15", 10) || 15
      : 15
  );

  $effect(() => {
    if (typeof window !== "undefined" && targetFps) {
      localStorage.setItem("preferred_stream_fps", targetFps.toString());
    }
  });

  let streamTimestamp = $state(Date.now());
  let isStreamLoading = $state(true);
  let isStreamError = $state(false);
  let videoContainer = $state(null);
  let isFullscreen = $state(false);

  // Visual Zone Calibration
  let isEditingZones = $state(false);
  let zones = $state([]);
  let selectedZoneIdx = $state(0);
  let activeDragHandle = $state(null); // { zoneIdx, ptIdx }
  let isSavingZones = $state(false);
  let zoneStatusMsg = $state("");
  let isZoneError = $state(false);

  // Viewport dimensions & cursor tracker
  let viewWidth = $state(640);
  let viewHeight = $state(480);
  let cursorX = $state(0);
  let cursorY = $state(0);


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

  async function loadCameras() {
    try {
      const res = await fetchCameras();
      if (res && Array.isArray(res.cameras) && res.cameras.length > 0) {
        const hasPrimary = res.cameras.some((c) => c.camera_id === "cam_primary");
        cameras = hasPrimary
          ? res.cameras
          : [
              { camera_id: "cam_primary", label: "Primary (Overhead Entrance)", is_active: true },
              ...res.cameras,
            ];
      }
    } catch (err) {
      console.warn("Failed to load camera mesh list:", err);
    }
  }

  async function handleAddCamera(e) {
    e.preventDefault();
    if (!newCamId.trim() || !newCamSource.trim()) {
      camErrorMsg = "Camera ID and Source are required.";
      return;
    }
    isSubmittingCam = true;
    camErrorMsg = "";
    try {
      await registerCamera({
        camera_id: newCamId.trim().toLowerCase().replace(/[^a-z0-9_]/g, "_"),
        source: newCamSource.trim(),
        role: newCamRole,
        label: newCamLabel.trim() || newCamId.trim(),
      });
      newCamId = "";
      newCamSource = "";
      newCamLabel = "";
      newCamRole = "general";
      isAddCameraOpen = false;
      await loadCameras();
      refreshStream();
    } catch (err) {
      camErrorMsg = err.message || "Failed to register camera";
    } finally {
      isSubmittingCam = false;
    }
  }

  async function handleRemoveCamera(camId) {
    if (!confirm(`Remove camera "${camId}" from mesh?`)) return;
    try {
      await unregisterCamera(camId);
      await loadCameras();
      refreshStream();
    } catch (err) {
      alert(`Failed to remove camera: ${err.message}`);
    }
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
    link.href = `/video/snapshot?camera_id=cam_primary&overlay_zones=${overlayZones}&overlay_detections=${overlayDetections}&t=${Date.now()}`;
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
    zones[zoneIdx].polygon[ptIdx] = [cursorX, cursorY];
  }

  function handleSvgMouseUp() {
    activeDragHandle = null;
  }

  $effect(() => {
    loadCameras();
    loadZones();

    const handleFsChange = () => {
      isFullscreen = !!document.fullscreenElement;
    };
    document.addEventListener("fullscreenchange", handleFsChange);

    return () => {
      document.removeEventListener("fullscreenchange", handleFsChange);
    };
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
        <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-900">Live Camera Stream</h2>
      </div>

      <div class="flex items-center bg-slate-50 border border-slate-200 rounded px-2 py-0.5 text-xs font-mono text-slate-700">
        <span class="text-slate-500 mr-1.5 uppercase font-semibold">CAMERAS:</span>
        <span class="font-bold text-slate-900">{cameras.length} ACTIVE</span>
      </div>

      <span class="px-2 py-0.5 text-xs font-mono font-semibold uppercase rounded border {isConnected && !isStreamError ? 'bg-slate-50 text-slate-800 border-slate-200' : 'bg-rose-50 text-rose-800 border-rose-200'}">
        {isConnected && !isStreamError ? 'ONLINE' : 'STANDBY'}
      </span>
      <span class="px-2 py-0.5 text-xs font-mono bg-sky-50 text-sky-800 border border-sky-200 rounded hidden sm:inline">
        YOLOv26n Active
      </span>
      {#if isEditingZones}
        <span class="px-2 py-0.5 text-xs font-mono font-semibold bg-amber-50 text-amber-800 border border-amber-300 rounded">
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
          onclick={() => { overlayZones = false; refreshStream(); }}
          title="Toggle ROI zone overlays on video stream"
        >
          <span class="w-2 h-2 rounded-full bg-sky-500"></span>
          <span>ROI ZONES</span>
        </button>
      {:else}
        <button 
          type="button"
          class="flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono rounded border border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100 cursor-pointer transition-colors"
          onclick={() => { overlayZones = true; refreshStream(); }}
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
          onclick={() => { overlayDetections = false; refreshStream(); }}
          title="Toggle YOLO bounding box overlays on video stream"
        >
          <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
          <span>YOLO BOXES</span>
        </button>
      {:else}
        <button 
          type="button"
          class="flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono rounded border border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100 cursor-pointer transition-colors"
          onclick={() => { overlayDetections = true; refreshStream(); }}
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
          onclick={startZoneEdit}
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
          onclick={addZone}
        >
          + NEW ZONE
        </button>
        <button 
          type="button" 
          class="px-2.5 py-1 text-xs font-mono bg-slate-100 text-slate-700 border border-slate-200 rounded hover:bg-slate-200 cursor-pointer"
          onclick={cancelZoneEdit}
        >
          CANCEL
        </button>
        <button 
          type="button" 
          class="px-2.5 py-1 text-xs font-mono bg-sky-600 text-white rounded hover:bg-sky-700 font-semibold disabled:opacity-50 cursor-pointer"
          onclick={saveZones} 
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
          onchange={refreshStream}
          aria-label="Stream target frames per second"
        />
      </div>

      <!-- Add Camera Toggle -->
      <button 
        type="button" 
        class="flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono bg-slate-50 text-slate-700 border border-slate-200 rounded hover:bg-slate-100 transition-colors cursor-pointer"
        onclick={() => { isAddCameraOpen = !isAddCameraOpen; }}
        title="Add camera node to mesh"
      >
        <svg class="w-3.5 h-3.5 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="12" y1="5" x2="12" y2="19"/>
          <line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        <span>CAMERA</span>
      </button>

      <!-- Action Buttons -->
      <button 
        type="button" 
        class="p-1.5 rounded text-slate-600 hover:text-sky-700 hover:bg-slate-100 border border-slate-200 transition-colors cursor-pointer"
        onclick={takeSnapshot} 
        title="Capture JPEG Snapshot"
        aria-label="Capture JPEG Snapshot"
      >
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
          <circle cx="12" cy="13" r="4"/>
        </svg>
      </button>

      <button 
        type="button" 
        class="p-1.5 rounded text-slate-600 hover:text-sky-700 hover:bg-slate-100 border border-slate-200 transition-colors cursor-pointer"
        onclick={refreshStream} 
        title="Reconnect Video Stream"
        aria-label="Reconnect Video Stream"
      >
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="23 4 23 10 17 10"/>
          <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
        </svg>
      </button>

      <button 
        type="button" 
        class="p-1.5 rounded text-slate-600 hover:text-sky-700 hover:bg-slate-100 border border-slate-200 transition-colors cursor-pointer"
        onclick={toggleFullscreen} 
        title="Toggle Fullscreen"
        aria-label="Toggle Fullscreen"
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

  <!-- Add Camera Drawer Form -->
  {#if isAddCameraOpen}
    <form 
      onsubmit={handleAddCamera}
      class="p-3 sm:p-4 bg-slate-50 border border-slate-200 rounded-md flex flex-col gap-3 shadow-xs"
    >
      <div class="flex items-center justify-between pb-2 border-b border-slate-200">
        <h3 class="text-xs font-mono font-semibold uppercase text-slate-800">Register New Camera Node</h3>
        <button 
          type="button" 
          class="text-xs font-mono text-slate-500 hover:text-slate-800 cursor-pointer"
          onclick={() => { isAddCameraOpen = false; camErrorMsg = ""; }}
        >
          Close
        </button>
      </div>

      {#if camErrorMsg}
        <div class="px-2.5 py-1 text-xs font-mono bg-rose-50 text-rose-800 border border-rose-200 rounded">
          {camErrorMsg}
        </div>
      {/if}

      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
        <div class="flex flex-col gap-1">
          <label for="cam-id-input" class="text-2xs font-mono uppercase text-slate-500 font-medium">Camera ID *</label>
          <input 
            id="cam-id-input"
            type="text" 
            placeholder="cam_aisle_2" 
            bind:value={newCamId}
            class="px-2.5 py-1 text-xs font-mono bg-white border border-slate-300 rounded focus:outline-none focus:border-sky-500"
            required
          />
        </div>

        <div class="flex flex-col gap-1">
          <label for="cam-src-input" class="text-2xs font-mono uppercase text-slate-500 font-medium">Source (RTSP / USB / MP4) *</label>
          <input 
            id="cam-src-input"
            type="text" 
            placeholder="rtsp://192.168.1.102:8080/live" 
            bind:value={newCamSource}
            class="px-2.5 py-1 text-xs font-mono bg-white border border-slate-300 rounded focus:outline-none focus:border-sky-500"
            required
          />
        </div>

        <div class="flex flex-col gap-1">
          <label for="cam-label-input" class="text-2xs font-mono uppercase text-slate-500 font-medium">Display Label</label>
          <input 
            id="cam-label-input"
            type="text" 
            placeholder="Aisle 2 - Snacks" 
            bind:value={newCamLabel}
            class="px-2.5 py-1 text-xs font-mono bg-white border border-slate-300 rounded focus:outline-none focus:border-sky-500"
          />
        </div>

        <div class="flex flex-col gap-1">
          <label for="cam-role-input" class="text-2xs font-mono uppercase text-slate-500 font-medium">Role</label>
          <select 
            id="cam-role-input"
            bind:value={newCamRole}
            class="px-2 py-1 text-xs font-mono bg-white border border-slate-300 rounded focus:outline-none focus:border-sky-500"
          >
            <option value="general">general</option>
            <option value="shelf">shelf</option>
            <option value="checkout">checkout</option>
            <option value="entrance">entrance</option>
          </select>
        </div>
      </div>

      <div class="flex items-center justify-end gap-2 pt-1">
        <button 
          type="button" 
          class="px-3 py-1 text-xs font-mono bg-white border border-slate-200 text-slate-600 rounded hover:bg-slate-100 cursor-pointer"
          onclick={() => { isAddCameraOpen = false; }}
        >
          Cancel
        </button>
        <button 
          type="submit" 
          class="px-3 py-1 text-xs font-mono bg-sky-600 text-white font-semibold rounded hover:bg-sky-700 disabled:opacity-50 cursor-pointer"
          disabled={isSubmittingCam}
        >
          {isSubmittingCam ? "Registering..." : "Add Camera Node"}
        </button>
      </div>
    </form>
  {/if}

  <!-- Dynamic Multi-Camera Stream Grid -->
  <div class="grid gap-3 w-full {cameras.length <= 1 ? 'grid-cols-1' : cameras.length === 2 ? 'grid-cols-1 md:grid-cols-2' : cameras.length === 3 ? 'grid-cols-1 md:grid-cols-3' : 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3'}">
    {#each cameras as cam (cam.camera_id)}
      {@const camStreamUrl = `/video/stream?camera_id=${cam.camera_id}&overlay_zones=${cam.camera_id === 'cam_primary' && !isEditingZones && overlayZones}&overlay_detections=${overlayDetections}&fps=${targetFps}&t=${streamTimestamp}`}
      <div class="relative w-full aspect-video bg-slate-950 rounded-md overflow-hidden flex items-center justify-center border border-slate-800">
        <img 
          src={camStreamUrl} 
          alt={cam.label || cam.camera_id} 
          class="w-full h-full object-contain select-none"
          onload={handleImageLoad}
          onerror={handleImageError}
        />

        <!-- Top Watermark & Info Overlay -->
        <div class="absolute top-2 sm:top-2.5 left-2 sm:left-2.5 right-2 sm:right-2.5 flex items-center justify-between gap-1 pointer-events-none text-xs font-mono z-10">
          <div class="flex items-center gap-1.5 bg-slate-950/80 backdrop-blur-xs border border-slate-800 text-slate-200 px-2 py-0.5 rounded shadow-sm">
            <span class="text-slate-300 font-semibold">{cam.label || cam.camera_id.toUpperCase()}</span>
          </div>

          <div class="flex items-center gap-1.5">
            {#if cam.camera_id !== 'cam_primary'}
              <button
                type="button"
                class="pointer-events-auto bg-slate-950/80 hover:bg-rose-950/80 text-slate-400 hover:text-rose-300 border border-slate-800 hover:border-rose-800/60 px-1.5 py-0.5 rounded transition-colors cursor-pointer text-[10px]"
                title="Remove camera node"
                onclick={() => handleRemoveCamera(cam.camera_id)}
              >
                ✕ REMOVE
              </button>
            {/if}

            {#if cam.camera_id === 'cam_primary' && isEditingZones}
              <div class="flex items-center gap-1.5 bg-amber-950/80 backdrop-blur-xs border border-amber-600/50 text-amber-200 px-2 sm:px-2.5 py-0.5 rounded shadow-sm">
                <span>CALIBRATING</span>
                <span class="text-amber-400 font-bold">X:{cursorX} Y:{cursorY}</span>
              </div>
            {/if}
          </div>
        </div>

        <!-- Interactive SVG ROI polygon editor for primary camera in calibration mode -->
        {#if cam.camera_id === 'cam_primary' && isEditingZones}
          <svg 
            class="absolute inset-0 w-full h-full cursor-crosshair select-none z-20 pointer-events-auto" 
            viewBox="0 0 {viewWidth} {viewHeight}"
            role="region"
            aria-label="Zone calibration canvas"
            onmousemove={handleSvgMouseMove}
            onmouseup={handleSvgMouseUp}
            onmouseleave={handleSvgMouseUp}
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
                onmousedown={() => selectedZoneIdx = zIdx}
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
                    onmousedown={(e) => handleSvgMouseDown(zIdx, ptIdx, e)}
                  />
                {/each}
              {/if}
            {/each}
          </svg>
        {/if}

        <!-- Bottom Stream HUD on each cell -->
        <div class="absolute bottom-2 sm:bottom-2.5 left-2 sm:left-2.5 right-2 sm:right-2.5 flex items-center justify-between gap-1 pointer-events-none text-xs font-mono z-10">
          <div class="flex items-center gap-1 sm:gap-1.5 bg-slate-900/90 backdrop-blur-xs border border-slate-700 text-slate-200 px-2 sm:px-2.5 py-0.5 sm:py-1 rounded shadow-md truncate">
            <span>{targetFps} FPS</span>
            <span class="text-slate-500">|</span>
            <span class="text-slate-300">{viewWidth}×{viewHeight}</span>
            <span class="text-slate-500 hidden sm:inline">|</span>
            <span class="text-sky-400 hidden sm:inline">YOLOv26n</span>
          </div>

          <div class="flex items-center gap-1 sm:gap-1.5 bg-slate-900/90 backdrop-blur-xs border border-slate-700 text-slate-300 px-2 sm:px-2.5 py-0.5 sm:py-1 rounded shadow-md shrink-0">
            {#if overlayZones && cam.camera_id === 'cam_primary'}
              <span class="text-sky-400 hidden md:inline">ZONES: ON</span>
            {/if}
            {#if overlayDetections}
              <span class="text-emerald-400 hidden md:inline">YOLO: ON</span>
            {/if}
            <span class="text-slate-300 font-semibold">FEED ACTIVE</span>
          </div>
        </div>
      </div>
    {/each}
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
          <button type="button" class="px-2.5 py-1 bg-white border border-slate-200 text-slate-700 rounded hover:bg-slate-100 cursor-pointer" onclick={addZone}>
            + Add Zone
          </button>
          <button type="button" class="px-2.5 py-1 bg-rose-50 border border-rose-200 text-rose-800 rounded hover:bg-rose-100 font-semibold cursor-pointer" onclick={() => removeZone(selectedZoneIdx)}>
            Delete
          </button>
        </div>
      {:else}
        <div class="flex items-center justify-between w-full">
          <span class="text-slate-500">No detection zones configured.</span>
          <button type="button" class="px-2.5 py-1 bg-sky-600 text-white rounded hover:bg-sky-700 cursor-pointer" onclick={addZone}>
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
