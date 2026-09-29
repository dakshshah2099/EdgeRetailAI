<script>
  import { onMount } from "svelte";
  import { 
    fetchSystemZones, 
    updateSystemZones, 
    fetchCameras, 
    registerCamera, 
    unregisterCamera,
    updateCameraSource,
    fetchPrimaryCameraSource
  } from "../lib/api.js";

  let { isConnected = true, occupancy = 0 } = $props();

  // Multi-camera mesh topology state
  let cameras = $state([
    { camera_id: "cam_primary", label: "Primary Store Feed", source: "0", role: "entrance", is_connected: true }
  ]);
  let cameraResolutions = $state({}); // { [camId]: { width, height } }
  let camTimestamps = $state({}); // { [camId]: number }
  let globalTimestamp = $state(Date.now());

  // Stream controls
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

  // Layout & focus state
  let focusedCamId = $state(null); // When set, focuses one stream full-width
  let videoContainer = null;
  let isFullscreen = $state(false);

  // Per-camera source editing state
  let editingSourceCamId = $state(null);
  let sourceInputs = $state({});
  let isUpdatingSource = $state({});
  let sourceStatusMsgs = $state({});

  // Zone calibration state (per-camera interactive calibration)
  let calibratingCamId = $state(null);
  let zones = $state([]);
  let selectedZoneIdx = $state(0);
  let activeDragHandle = $state(null); // { zoneIdx, ptIdx }
  let cursorX = $state(0);
  let cursorY = $state(0);
  let viewWidth = $state(640);
  let viewHeight = $state(480);
  let isSavingZones = $state(false);
  let zoneStatusMsg = $state("");
  let isZoneError = $state(false);

  // Add camera modal state
  let isAddCameraOpen = $state(false);
  let newCamId = $state("");
  let newCamSource = $state("");
  let newCamLabel = $state("");
  let newCamRole = $state("general");
  let isSubmittingCam = $state(false);
  let addCamErrorMsg = $state("");

  const zoneColorMap = {
    entry_exit: {
      stroke: "#059669",
      fill: "rgba(5, 150, 105, 0.22)",
      text: "#059669",
      badge: "bg-emerald-50 text-emerald-800 border-emerald-300",
    },
    shelf: {
      stroke: "#0284c7",
      fill: "rgba(2, 132, 199, 0.22)",
      text: "#0284c7",
      badge: "bg-sky-50 text-sky-800 border-sky-300",
    },
    checkout: {
      stroke: "#d97706",
      fill: "rgba(217, 119, 6, 0.22)",
      text: "#d97706",
      badge: "bg-amber-50 text-amber-800 border-amber-300",
    },
    product_display: {
      stroke: "#e11d48",
      fill: "rgba(225, 29, 72, 0.22)",
      text: "#e11d48",
      badge: "bg-rose-50 text-rose-800 border-rose-300",
    },
  };

  const roleBadgeMap = {
    entrance: "bg-emerald-50 text-emerald-800 border-emerald-300",
    shelf: "bg-sky-50 text-sky-800 border-sky-300",
    checkout: "bg-amber-50 text-amber-800 border-amber-300",
    general: "bg-purple-50 text-purple-800 border-purple-300",
  };

  function getZoneTheme(zoneType) {
    return zoneColorMap[zoneType] || zoneColorMap.shelf;
  }

  function getRoleBadge(role) {
    return roleBadgeMap[role] || roleBadgeMap.general;
  }

  onMount(async () => {
    await loadCameras();
    await loadZones();
  });

  async function loadCameras() {
    try {
      const res = await fetchCameras();
      let loaded = res && Array.isArray(res.cameras) ? [...res.cameras] : [];
      const primaryIdx = loaded.findIndex((c) => c.camera_id === "cam_primary");
      if (primaryIdx === -1) {
        let primSrc = "0";
        try {
          const pRes = await fetchPrimaryCameraSource();
          if (pRes && pRes.source) primSrc = pRes.source;
        } catch {}
        loaded.unshift({
          camera_id: "cam_primary",
          label: "Primary Store Feed",
          source: primSrc,
          role: "entrance",
          is_connected: isConnected,
        });
      }

      cameras = loaded;
      // Initialize source inputs
      const nextInputs = { ...sourceInputs };
      for (const cam of loaded) {
        if (!nextInputs[cam.camera_id]) {
          nextInputs[cam.camera_id] = cam.source || "";
        }
      }
      sourceInputs = nextInputs;
    } catch (err) {
      console.warn("Failed to load cameras list:", err);
    }
  }

  async function loadZones() {
    try {
      const data = await fetchSystemZones();
      zones = Array.isArray(data) ? data : [];
    } catch (err) {
      console.error("Failed to load zones:", err);
    }
  }

  function refreshAllStreams() {
    globalTimestamp = Date.now();
    const nextStamps = {};
    for (const c of cameras) {
      nextStamps[c.camera_id] = Date.now();
    }
    camTimestamps = nextStamps;
  }

  function refreshCameraStream(camId) {
    camTimestamps = { ...camTimestamps, [camId]: Date.now() };
  }

  async function handleApplySource(camId, targetSource = null) {
    const src = (targetSource !== null ? targetSource : (sourceInputs[camId] || "")).trim();
    if (!src) {
      sourceStatusMsgs = {
        ...sourceStatusMsgs,
        [camId]: { text: "Camera source cannot be empty. Specify RTSP URL, device index (0), or video file.", isError: true }
      };
      return;
    }

    isUpdatingSource = { ...isUpdatingSource, [camId]: true };
    sourceStatusMsgs = {
      ...sourceStatusMsgs,
      [camId]: { text: `Connecting to "${src}"...`, isError: false }
    };

    try {
      await updateCameraSource(camId, src);
      cameras = cameras.map((c) => (c.camera_id === camId ? { ...c, source: src } : c));
      sourceInputs = { ...sourceInputs, [camId]: src };
      sourceStatusMsgs = {
        ...sourceStatusMsgs,
        [camId]: { text: `✓ Source saved to config.yaml. Stream reconnecting...`, isError: false }
      };
      refreshCameraStream(camId);
      await loadCameras();
      setTimeout(() => {
        // Clear message after 4s
        const cur = { ...sourceStatusMsgs };
        delete cur[camId];
        sourceStatusMsgs = cur;
      }, 4000);
    } catch (err) {
      sourceStatusMsgs = {
        ...sourceStatusMsgs,
        [camId]: { text: `Error updating source: ${err.message}`, isError: true }
      };
    } finally {
      isUpdatingSource = { ...isUpdatingSource, [camId]: false };
    }
  }

  function handleSelectSourcePreset(camId, presetVal) {
    sourceInputs = { ...sourceInputs, [camId]: presetVal };
    handleApplySource(camId, presetVal);
  }

  function toggleSourceEditor(camId) {
    if (editingSourceCamId === camId) {
      editingSourceCamId = null;
    } else {
      editingSourceCamId = camId;
      const cam = cameras.find((c) => c.camera_id === camId);
      if (cam && cam.source) {
        sourceInputs = { ...sourceInputs, [camId]: cam.source };
      }
    }
  }

  // Zone Calibration Controls
  function startCalibration(camId) {
    calibratingCamId = camId;
    editingSourceCamId = null;
    zoneStatusMsg = "";
    isZoneError = false;

    const res = cameraResolutions[camId];
    viewWidth = res ? res.width : 640;
    viewHeight = res ? res.height : 480;

    // Pick first zone belonging to this camera
    const camZoneIndices = zones
      .map((z, idx) => ((z.camera_id || "cam_primary") === camId ? idx : -1))
      .filter((i) => i !== -1);

    selectedZoneIdx = camZoneIndices.length > 0 ? camZoneIndices[0] : -1;
  }

  function cancelCalibration() {
    calibratingCamId = null;
    loadZones();
  }

  async function saveCalibration(camId) {
    isSavingZones = true;
    zoneStatusMsg = "";
    isZoneError = false;
    try {
      // Send all zones for this camera
      const camZones = zones.filter((z) => (z.camera_id || "cam_primary") === camId);
      await updateSystemZones(camZones, viewWidth, viewHeight, { camera_id: camId });
      zoneStatusMsg = `✓ Zones saved for [${camId}] (${viewWidth}×${viewHeight}) in config.yaml.`;
      isZoneError = false;
      refreshCameraStream(camId);
      await loadZones();
      setTimeout(() => {
        if (calibratingCamId === camId) {
          calibratingCamId = null;
        }
      }, 1200);
    } catch (err) {
      zoneStatusMsg = `Error saving zones: ${err.message}`;
      isZoneError = true;
    } finally {
      isSavingZones = false;
    }
  }

  function addZoneForCamera(camId) {
    const newId = `zone_${Date.now().toString().slice(-4)}`;
    const x1 = Math.round(viewWidth * 0.2);
    const y1 = Math.round(viewHeight * 0.2);
    const x2 = Math.round(viewWidth * 0.5);
    const y2 = Math.round(viewHeight * 0.5);
    const camZoneCount = zones.filter((z) => (z.camera_id || "cam_primary") === camId).length;

    const newZone = {
      zone_id: newId,
      zone_type: "shelf",
      label: `Zone ${camZoneCount + 1}`,
      camera_id: camId,
      polygon: [
        [x1, y1],
        [x2, y1],
        [x2, y2],
        [x1, y2],
      ],
    };
    zones = [...zones, newZone];
    selectedZoneIdx = zones.length - 1;
  }

  function removeZone(idx) {
    zones = zones.filter((_, i) => i !== idx);
    const camZoneIndices = zones
      .map((z, i) => ((z.camera_id || "cam_primary") === calibratingCamId ? i : -1))
      .filter((i) => i !== -1);
    selectedZoneIdx = camZoneIndices.length > 0 ? camZoneIndices[0] : -1;
  }

  function handleSvgMouseDown(zoneIdx, ptIdx, e) {
    e.stopPropagation();
    selectedZoneIdx = zoneIdx;
    activeDragHandle = { zoneIdx, ptIdx };
  }

  function handleSvgMouseMove(e) {
    const svg = e.currentTarget;
    if (svg && typeof svg.createSVGPoint === "function") {
      const pt = svg.createSVGPoint();
      pt.x = e.clientX;
      pt.y = e.clientY;
      const ctm = svg.getScreenCTM();
      if (ctm) {
        const svgP = pt.matrixTransform(ctm.inverse());
        cursorX = Math.round(Math.max(0, Math.min(viewWidth, svgP.x)));
        cursorY = Math.round(Math.max(0, Math.min(viewHeight, svgP.y)));
      } else {
        const svgRect = svg.getBoundingClientRect();
        const scaleX = viewWidth / (svgRect.width || 1);
        const scaleY = viewHeight / (svgRect.height || 1);
        cursorX = Math.round(Math.max(0, Math.min(viewWidth, (e.clientX - svgRect.left) * scaleX)));
        cursorY = Math.round(Math.max(0, Math.min(viewHeight, (e.clientY - svgRect.top) * scaleY)));
      }
    }

    if (!activeDragHandle) return;
    const { zoneIdx, ptIdx } = activeDragHandle;
    if (zones[zoneIdx] && zones[zoneIdx].polygon && zones[zoneIdx].polygon[ptIdx]) {
      zones[zoneIdx].polygon[ptIdx] = [cursorX, cursorY];
    }
  }

  function handleSvgMouseUp() {
    activeDragHandle = null;
  }

  function handleImageLoad(camId, e) {
    if (e.target && e.target.naturalWidth) {
      const newW = e.target.naturalWidth;
      const newH = e.target.naturalHeight;
      if (newW > 0 && newH > 0) {
        cameraResolutions[camId] = { width: newW, height: newH };
        if (camId === calibratingCamId && (newW !== viewWidth || newH !== viewHeight)) {
          viewWidth = newW;
          viewHeight = newH;
        }
      }
    }
  }

  function toggleFocus(camId) {
    focusedCamId = focusedCamId === camId ? null : camId;
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

  function takeSnapshot(camId) {
    const link = document.createElement("a");
    link.href = `/video/snapshot?camera_id=${camId}&overlay_zones=${overlayZones}&overlay_detections=${overlayDetections}&t=${Date.now()}`;
    link.download = `snapshot_${camId}_${new Date().toISOString().replace(/[:.]/g, "-")}.jpg`;
    link.target = "_blank";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  async function handleAddCamera(e) {
    if (e) e.preventDefault();
    if (!newCamId.trim() || !newCamSource.trim()) {
      addCamErrorMsg = "Camera ID and Source URI are required.";
      return;
    }

    isSubmittingCam = true;
    addCamErrorMsg = "";
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
      refreshAllStreams();
    } catch (err) {
      addCamErrorMsg = err.message || "Failed to register camera node";
    } finally {
      isSubmittingCam = false;
    }
  }

  async function handleRemoveCamera(camId) {
    if (!confirm(`Are you sure you want to remove camera "${camId}" from the active mesh?`)) return;
    try {
      await unregisterCamera(camId);
      if (focusedCamId === camId) focusedCamId = null;
      if (calibratingCamId === camId) calibratingCamId = null;
      await loadCameras();
      refreshAllStreams();
    } catch (err) {
      alert(`Failed to remove camera: ${err.message}`);
    }
  }

  function getCamZones(camId) {
    return zones.filter((z) => (z.camera_id || "cam_primary") === camId);
  }
</script>

<svelte:document onfullscreenchange={() => { isFullscreen = !!document.fullscreenElement; }} />

<div 
  class="flex flex-col gap-3.5 w-full {isFullscreen ? 'fixed inset-0 z-50 bg-slate-950 p-4 overflow-y-auto' : ''}" 
  bind:this={videoContainer}
>
  <!-- Global Toolbar Header -->
  <div class="bg-white border border-slate-200 rounded-lg shadow-xs p-3 sm:p-4 flex items-center justify-between flex-wrap gap-3">
    <div class="flex items-center gap-2.5 sm:gap-3 flex-wrap">
      <div class="flex items-center gap-2">
        <span class="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
        <h2 class="text-sm font-semibold tracking-tight text-slate-900 uppercase">
          Simultaneous Camera Streams ({cameras.length})
        </h2>
      </div>

      <div class="flex items-center bg-slate-50 border border-slate-200 rounded px-2.5 py-0.5 text-xs font-mono text-slate-700">
        <span class="text-slate-500 mr-1.5 uppercase font-semibold">GRID LAYOUT:</span>
        <span class="font-bold text-slate-900">{focusedCamId ? 'FOCUSED SINGLE' : `${cameras.length} CHANNELS`}</span>
      </div>

      <span class="px-2.5 py-0.5 text-xs font-mono font-semibold uppercase rounded border bg-sky-50 text-sky-800 border-sky-200">
        YOLOv26n Parallel Ingest
      </span>

      {#if calibratingCamId}
        <span class="px-2.5 py-0.5 text-xs font-mono font-semibold bg-amber-50 text-amber-900 border border-amber-300 rounded flex items-center gap-1.5 animate-pulse">
          <span class="w-2 h-2 rounded-full bg-amber-500"></span>
          CALIBRATING [{calibratingCamId}]
        </span>
      {/if}
    </div>

    <!-- Global View Controls -->
    <div class="flex items-center gap-2 flex-wrap">
      <!-- Unfocus button if in focused mode -->
      {#if focusedCamId}
        <button
          type="button"
          class="flex items-center gap-1.5 px-3 py-1 text-xs font-mono rounded bg-slate-100 text-slate-800 hover:bg-slate-200 border border-slate-300 font-semibold cursor-pointer transition-colors"
          onclick={() => focusedCamId = null}
        >
          <span>← BACK TO ALL STREAMS</span>
        </button>
      {/if}

      <!-- ROI Zones Toggle -->
      <button 
        type="button"
        class="flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono rounded border transition-colors cursor-pointer {overlayZones ? 'border-sky-300 bg-sky-50 text-sky-800 font-semibold' : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100'}"
        onclick={() => overlayZones = !overlayZones}
        title="Toggle configured zone polygons overlay"
      >
        <span class="w-2 h-2 rounded-full {overlayZones ? 'bg-sky-500' : 'bg-slate-400'}"></span>
        <span>ZONES</span>
      </button>

      <!-- YOLO Boxes Toggle -->
      <button 
        type="button"
        class="flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono rounded border transition-colors cursor-pointer {overlayDetections ? 'border-emerald-300 bg-emerald-50 text-emerald-800 font-semibold' : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100'}"
        onclick={() => overlayDetections = !overlayDetections}
        title="Toggle live YOLO person bounding boxes overlay"
      >
        <span class="w-2 h-2 rounded-full {overlayDetections ? 'bg-emerald-500' : 'bg-slate-400'}"></span>
        <span>YOLO BOXES</span>
      </button>

      <!-- FPS Selector -->
      <div class="flex items-center bg-slate-50 border border-slate-200 rounded px-2 py-0.5 text-xs font-mono text-slate-700">
        <span class="text-slate-500 mr-1">FPS:</span>
        <input 
          type="number" 
          min="1" 
          max="30" 
          class="w-8 bg-transparent text-slate-900 font-semibold focus:outline-none"
          bind:value={targetFps} 
          onchange={refreshAllStreams}
          aria-label="Stream target frames per second"
        />
      </div>

      <!-- Add Camera Stream Button -->
      <button 
        type="button" 
        class="flex items-center gap-1.5 px-3 py-1 text-xs font-mono bg-sky-600 text-white rounded hover:bg-sky-700 font-semibold transition-colors cursor-pointer shadow-2xs"
        onclick={() => { isAddCameraOpen = !isAddCameraOpen; }}
        title="Add new camera stream to dynamic grid"
      >
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="12" y1="5" x2="12" y2="19"/>
          <line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        <span>+ ADD STREAM</span>
      </button>

      <!-- Reconnect All -->
      <button 
        type="button" 
        class="p-1.5 rounded text-slate-600 hover:text-sky-700 hover:bg-slate-100 border border-slate-200 transition-colors cursor-pointer"
        onclick={refreshAllStreams} 
        title="Reconnect All Video Streams"
        aria-label="Reconnect All Video Streams"
      >
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="23 4 23 10 17 10"/>
          <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
        </svg>
      </button>

      <!-- Fullscreen Grid -->
      <button 
        type="button" 
        class="p-1.5 rounded text-slate-600 hover:text-sky-700 hover:bg-slate-100 border border-slate-200 transition-colors cursor-pointer"
        onclick={toggleFullscreen} 
        title="Toggle Fullscreen Grid"
        aria-label="Toggle Fullscreen Grid"
      >
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
        </svg>
      </button>
    </div>
  </div>

  <!-- Add Camera Stream Drawer / Modal Form -->
  {#if isAddCameraOpen}
    <form 
      onsubmit={handleAddCamera}
      class="p-4 bg-slate-50 border border-sky-200 rounded-lg flex flex-col gap-3 shadow-xs font-mono text-xs"
    >
      <div class="flex items-center justify-between pb-2 border-b border-slate-200">
        <div class="flex items-center gap-2">
          <span class="w-2 h-2 rounded-full bg-sky-500"></span>
          <h3 class="text-xs font-semibold uppercase text-slate-800">Add New Stream to Dynamic Grid</h3>
        </div>
        <button 
          type="button" 
          class="text-xs text-slate-500 hover:text-slate-800 cursor-pointer font-sans"
          onclick={() => { isAddCameraOpen = false; addCamErrorMsg = ""; }}
        >
          ✕ Close
        </button>
      </div>

      {#if addCamErrorMsg}
        <div class="px-3 py-1.5 text-xs bg-rose-50 text-rose-800 border border-rose-200 rounded">
          {addCamErrorMsg}
        </div>
      {/if}

      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <div class="flex flex-col gap-1">
          <label for="new-cam-id" class="text-2xs uppercase text-slate-500 font-semibold">Camera Node ID *</label>
          <input 
            id="new-cam-id"
            type="text" 
            placeholder="cam_checkout_2" 
            bind:value={newCamId}
            class="px-2.5 py-1.5 bg-white border border-slate-300 rounded focus:outline-none focus:border-sky-500 font-mono text-slate-900"
            required
          />
        </div>

        <div class="flex flex-col gap-1">
          <label for="new-cam-source" class="text-2xs uppercase text-slate-500 font-semibold">Stream Source (RTSP / USB / MP4) *</label>
          <input 
            id="new-cam-source"
            type="text" 
            placeholder="rtsp://192.168.1.102:8080/live or 0" 
            bind:value={newCamSource}
            class="px-2.5 py-1.5 bg-white border border-slate-300 rounded focus:outline-none focus:border-sky-500 font-mono text-slate-900"
            required
          />
        </div>

        <div class="flex flex-col gap-1">
          <label for="new-cam-label" class="text-2xs uppercase text-slate-500 font-semibold">Display Label</label>
          <input 
            id="new-cam-label"
            type="text" 
            placeholder="Checkout Counter 2" 
            bind:value={newCamLabel}
            class="px-2.5 py-1.5 bg-white border border-slate-300 rounded focus:outline-none focus:border-sky-500 font-mono text-slate-900"
          />
        </div>

        <div class="flex flex-col gap-1">
          <label for="new-cam-role" class="text-2xs uppercase text-slate-500 font-semibold">Analytics Role</label>
          <select 
            id="new-cam-role"
            bind:value={newCamRole}
            class="px-2.5 py-1.5 bg-white border border-slate-300 rounded focus:outline-none focus:border-sky-500 font-mono text-slate-900 cursor-pointer"
          >
            <option value="general">general (People Tracking)</option>
            <option value="shelf">shelf (Stock & SKU Analysis)</option>
            <option value="checkout">checkout (Queue Intelligence)</option>
            <option value="entrance">entrance (Footfall Analytics)</option>
          </select>
        </div>
      </div>

      <!-- Quick Preset Suggestions for New Camera -->
      <div class="flex items-center gap-1.5 flex-wrap pt-1">
        <span class="text-slate-400 text-2xs uppercase">Presets:</span>
        <button 
          type="button" 
          class="px-2 py-0.5 bg-white border border-slate-200 hover:bg-sky-50 text-2xs text-slate-700 rounded cursor-pointer transition-colors"
          onclick={() => newCamSource = 'rtsp://192.168.1.100:8080/h264_pcm.sdp'}
        >
          Phone RTSP
        </button>
        <button 
          type="button" 
          class="px-2 py-0.5 bg-white border border-slate-200 hover:bg-sky-50 text-2xs text-slate-700 rounded cursor-pointer transition-colors"
          onclick={() => newCamSource = '0'}
        >
          Webcam (0)
        </button>
        <button 
          type="button" 
          class="px-2 py-0.5 bg-white border border-slate-200 hover:bg-sky-50 text-2xs text-slate-700 rounded cursor-pointer transition-colors"
          onclick={() => newCamSource = 'tests/fixtures/sample_video.mp4'}
        >
          Walkthrough MP4
        </button>
      </div>

      <div class="flex items-center justify-end gap-2 pt-2 border-t border-slate-200">
        <button 
          type="button" 
          class="px-3 py-1 bg-white border border-slate-200 text-slate-600 rounded hover:bg-slate-100 cursor-pointer"
          onclick={() => { isAddCameraOpen = false; }}
        >
          Cancel
        </button>
        <button 
          type="submit" 
          class="px-4 py-1 bg-sky-600 text-white font-semibold rounded hover:bg-sky-700 disabled:opacity-50 cursor-pointer shadow-2xs"
          disabled={isSubmittingCam}
        >
          {isSubmittingCam ? "Connecting Stream..." : "Register Stream & Start Analysis"}
        </button>
      </div>
    </form>
  {/if}

  <!-- DYNAMIC MULTI-STREAM GRID -->
  <div 
    class="grid gap-4 w-full {focusedCamId ? 'grid-cols-1' : cameras.length === 1 ? 'grid-cols-1 max-w-4xl mx-auto' : cameras.length === 2 ? 'grid-cols-1 lg:grid-cols-2' : cameras.length === 3 ? 'grid-cols-1 md:grid-cols-2 xl:grid-cols-3' : 'grid-cols-1 md:grid-cols-2 xl:grid-cols-3'}"
  >
    {#each cameras as cam (cam.camera_id)}
      {@const isCalibratingThis = calibratingCamId === cam.camera_id}
      {@const isEditingSource = editingSourceCamId === cam.camera_id}
      {@const camZones = getCamZones(cam.camera_id)}
      {@const isFocused = focusedCamId === cam.camera_id}
      {@const camStreamUrl = `/video/stream?camera_id=${cam.camera_id}&overlay_zones=${!isCalibratingThis && overlayZones}&overlay_detections=${overlayDetections}&fps=${targetFps}&t=${camTimestamps[cam.camera_id] || globalTimestamp}`}

      {#if !focusedCamId || isFocused}
        <div class="bg-white border rounded-lg shadow-xs overflow-hidden flex flex-col transition-all duration-150 {isCalibratingThis ? 'border-amber-400 ring-2 ring-amber-400/50' : 'border-slate-200'}">
          <!-- Card Header Bar -->
          <div class="px-3 py-2 bg-slate-50 border-b border-slate-100 flex items-center justify-between flex-wrap gap-2 text-xs font-mono">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="w-2 h-2 rounded-full {cam.is_connected !== false ? 'bg-emerald-500' : 'bg-amber-400'}"></span>
              <span class="font-bold text-slate-900 truncate max-w-[200px]" title={cam.label || cam.camera_id}>
                {cam.label || cam.camera_id}
              </span>
              <span class="text-slate-400">[{cam.camera_id}]</span>
              <span class="px-1.5 py-0.5 rounded text-[10px] uppercase font-semibold border {getRoleBadge(cam.role)}">
                {cam.role || 'general'}
              </span>
            </div>

            <!-- Per-Camera Toolbar -->
            <div class="flex items-center gap-1.5">
              <!-- Calibrate Button -->
              {#if isCalibratingThis}
                <button
                  type="button"
                  class="px-2 py-0.5 text-2xs font-bold rounded bg-amber-500 text-white hover:bg-amber-600 transition-colors cursor-pointer shadow-2xs"
                  onclick={cancelCalibration}
                >
                  ✓ DONE CALIBRATING
                </button>
              {:else}
                <button
                  type="button"
                  class="px-2 py-0.5 text-2xs font-semibold rounded bg-white text-slate-700 hover:bg-amber-50 hover:text-amber-900 border border-slate-200 hover:border-amber-300 transition-colors cursor-pointer"
                  onclick={() => startCalibration(cam.camera_id)}
                  title="Calibrate zones and bounding boxes for this camera"
                >
                  CALIBRATE
                </button>
              {/if}

              <!-- Source Toggle Button -->
              <button
                type="button"
                class="px-2 py-0.5 text-2xs font-semibold rounded bg-white text-slate-700 hover:bg-slate-100 border border-slate-200 transition-colors cursor-pointer {isEditingSource ? 'bg-slate-100 border-slate-300 font-bold' : ''}"
                onclick={() => toggleSourceEditor(cam.camera_id)}
                title="Change source RTSP / USB URL for this camera"
              >
                SOURCE
              </button>

              <!-- Snapshot Button -->
              <button
                type="button"
                class="p-1 rounded text-slate-600 hover:text-sky-700 hover:bg-slate-100 border border-slate-200 transition-colors cursor-pointer"
                onclick={() => takeSnapshot(cam.camera_id)}
                title="Save Snapshot"
              >
                <svg class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
                  <circle cx="12" cy="13" r="4"/>
                </svg>
              </button>

              <!-- Focus / Expand Button -->
              <button
                type="button"
                class="p-1 rounded text-slate-600 hover:text-sky-700 hover:bg-slate-100 border border-slate-200 transition-colors cursor-pointer {isFocused ? 'bg-sky-50 text-sky-800' : ''}"
                onclick={() => toggleFocus(cam.camera_id)}
                title={isFocused ? "Restore Grid" : "Focus this Camera"}
              >
                {#if isFocused}
                  <svg class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="4 14 10 14 10 20"/>
                    <polyline points="20 10 14 10 14 4"/>
                    <line x1="14" y1="10" x2="21" y2="3"/>
                    <line x1="3" y1="21" x2="10" y2="14"/>
                  </svg>
                {:else}
                  <svg class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="15 3 21 3 21 9"/>
                    <polyline points="9 21 3 21 3 15"/>
                    <line x1="21" y1="3" x2="14" y2="10"/>
                    <line x1="3" y1="21" x2="10" y2="14"/>
                  </svg>
                {/if}
              </button>

              <!-- Remove Camera (non-primary only) -->
              {#if cam.camera_id !== 'cam_primary'}
                <button
                  type="button"
                  class="p-1 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50 border border-slate-200 transition-colors cursor-pointer"
                  onclick={() => handleRemoveCamera(cam.camera_id)}
                  title="Remove this camera node"
                >
                  <svg class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              {/if}
            </div>
          </div>

          <!-- Video Stream Canvas Container -->
          <div class="relative w-full aspect-video bg-slate-950 flex items-center justify-center overflow-hidden select-none">
            <img 
              src={camStreamUrl} 
              alt={cam.label || cam.camera_id} 
              class="w-full h-full object-contain pointer-events-none select-none"
              onload={(e) => handleImageLoad(cam.camera_id, e)}
            />

            <!-- Top HUD Badge on Video -->
            <div class="absolute top-2 left-2 right-2 flex items-center justify-between pointer-events-none text-2xs font-mono z-10">
              <div class="flex items-center gap-1.5 bg-slate-950/80 backdrop-blur-xs border border-slate-800 text-slate-200 px-2 py-0.5 rounded shadow-sm">
                <span class="text-emerald-400 font-semibold">• LIVE INGEST</span>
                <span class="text-slate-600">|</span>
                <span class="text-slate-300">{cam.source ? (cam.source.length > 25 ? cam.source.slice(0, 22) + '...' : cam.source) : 'device 0'}</span>
              </div>

              {#if isCalibratingThis}
                <div class="flex items-center gap-1 bg-amber-950/90 backdrop-blur-xs border border-amber-600/70 text-amber-200 px-2 py-0.5 rounded shadow-sm pointer-events-auto">
                  <span>EDITING ZONES</span>
                  <span class="text-amber-400 font-bold">X:{cursorX} Y:{cursorY}</span>
                </div>
              {/if}
            </div>

            <!-- Interactive SVG Zone Overlay for active calibrating camera -->
            {#if isCalibratingThis}
              <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
              <svg 
                class="absolute inset-0 w-full h-full cursor-crosshair select-none z-20 pointer-events-auto" 
                viewBox="0 0 {viewWidth} {viewHeight}"
                role="application"
                aria-label="Interactive zone calibration canvas"
                onmousemove={handleSvgMouseMove}
                onmouseup={handleSvgMouseUp}
                onmouseleave={handleSvgMouseUp}
              >
                {#each zones as zone, zIdx (zone.zone_id || zIdx)}
                  {#if (zone.camera_id || "cam_primary") === cam.camera_id}
                    {@const isSel = zIdx === selectedZoneIdx}
                    {@const theme = getZoneTheme(zone.zone_type)}
                    {@const ptsStr = zone.polygon.map((p) => p.join(',')).join(' ')}
                    <!-- svelte-ignore a11y_no_static_element_interactions -->
                    <polygon
                      points={ptsStr}
                      stroke={theme.stroke}
                      stroke-width={isSel ? '2.5' : '1.5'}
                      stroke-dasharray={isSel ? '4 2' : 'none'}
                      fill={theme.fill}
                      role="button"
                      tabindex="0"
                      aria-label={zone.label || `Zone ${zIdx + 1}`}
                      class="transition-all cursor-pointer focus:outline-none"
                      onmousedown={() => selectedZoneIdx = zIdx}
                      onkeydown={(e) => e.key === 'Enter' && (selectedZoneIdx = zIdx)}
                    />
                    <text
                      x={zone.polygon[0][0]}
                      y={Math.max(16, zone.polygon[0][1] - 6)}
                      class="fill-white font-mono text-xs font-bold drop-shadow"
                    >
                      {zone.label || zone.zone_id} ({zone.zone_type})
                    </text>

                    {#if isSel}
                      {#each zone.polygon as pt, ptIdx (`${zone.zone_id || zIdx}_pt_${ptIdx}`)}
                        <!-- svelte-ignore a11y_no_static_element_interactions -->
                        <circle
                          cx={pt[0]}
                          cy={pt[1]}
                          r="6"
                          fill={theme.stroke}
                          role="button"
                          tabindex="0"
                          aria-label={`Vertex ${ptIdx + 1} of ${zone.label || `Zone ${zIdx + 1}`}`}
                          class="stroke-2 stroke-white cursor-grab hover:scale-125 transition-transform focus:outline-none"
                          onmousedown={(e) => handleSvgMouseDown(zIdx, ptIdx, e)}
                        />
                      {/each}
                    {/if}
                  {/if}
                {/each}
              </svg>
            {/if}

            <!-- Bottom Stream Stats HUD -->
            <div class="absolute bottom-2 left-2 right-2 flex items-center justify-between pointer-events-none text-2xs font-mono z-10">
              <div class="flex items-center gap-1.5 bg-slate-900/90 backdrop-blur-xs border border-slate-800 text-slate-300 px-2 py-0.5 rounded shadow-sm">
                <span>{targetFps} FPS</span>
                <span class="text-slate-600">|</span>
                <span>{(cameraResolutions[cam.camera_id]?.width || 640)}×{(cameraResolutions[cam.camera_id]?.height || 480)}</span>
                <span class="text-slate-600">|</span>
                <span class="text-sky-400">YOLOv26n</span>
              </div>

              <div class="flex items-center gap-1.5 bg-slate-900/90 backdrop-blur-xs border border-slate-800 text-slate-300 px-2 py-0.5 rounded shadow-sm">
                <span class="text-amber-400 font-semibold">{camZones.length} ZONES</span>
                <span class="text-slate-600">|</span>
                <span class="text-emerald-400">ANALYSIS LIVE</span>
              </div>
            </div>
          </div>

          <!-- Per-Camera Inline Source Editor Drawer -->
          {#if isEditingSource}
            <div class="p-3 bg-amber-50/70 border-t border-amber-200 flex flex-col gap-2 font-mono text-xs">
              <div class="flex items-center justify-between text-2xs font-semibold uppercase text-amber-900">
                <span>Stream Source URI / Device Index for [{cam.camera_id}]:</span>
                <span class="text-slate-500 font-normal lowercase italic">persists to config.yaml</span>
              </div>

              <div class="flex flex-col sm:flex-row gap-2">
                <input 
                  type="text" 
                  bind:value={sourceInputs[cam.camera_id]}
                  placeholder="rtsp://192.168.1.100:8080/h264_pcm.sdp or 0 or video.mp4"
                  class="flex-1 bg-white border border-amber-300 rounded px-2.5 py-1 text-xs font-mono text-slate-900 focus:outline-none focus:border-amber-500 shadow-2xs"
                  onkeydown={(e) => e.key === 'Enter' && handleApplySource(cam.camera_id)}
                />
                <button 
                  type="button" 
                  class="px-3 py-1 bg-amber-600 hover:bg-amber-700 text-white font-semibold rounded cursor-pointer transition-colors disabled:opacity-50 shrink-0 shadow-2xs"
                  onclick={() => handleApplySource(cam.camera_id)}
                  disabled={isUpdatingSource[cam.camera_id]}
                >
                  {isUpdatingSource[cam.camera_id] ? 'Reconnecting...' : 'Apply & Reconnect'}
                </button>
              </div>

              <!-- Quick Presets -->
              <div class="flex items-center gap-1.5 flex-wrap">
                <span class="text-slate-500 text-2xs uppercase">Presets:</span>
                <button 
                  type="button" 
                  class="px-2 py-0.5 bg-white border border-amber-200 hover:bg-amber-100 text-2xs text-slate-700 rounded cursor-pointer"
                  onclick={() => handleSelectSourcePreset(cam.camera_id, 'rtsp://192.168.1.100:8080/h264_pcm.sdp')}
                >
                  Phone RTSP
                </button>
                <button 
                  type="button" 
                  class="px-2 py-0.5 bg-white border border-amber-200 hover:bg-amber-100 text-2xs text-slate-700 rounded cursor-pointer"
                  onclick={() => handleSelectSourcePreset(cam.camera_id, '0')}
                >
                  Webcam (0)
                </button>
                <button 
                  type="button" 
                  class="px-2 py-0.5 bg-white border border-amber-200 hover:bg-amber-100 text-2xs text-slate-700 rounded cursor-pointer"
                  onclick={() => handleSelectSourcePreset(cam.camera_id, 'tests/fixtures/sample_video.mp4')}
                >
                  Walkthrough MP4
                </button>
              </div>

              {#if sourceStatusMsgs[cam.camera_id]}
                <div class="px-2.5 py-1 rounded text-2xs border {sourceStatusMsgs[cam.camera_id].isError ? 'bg-rose-50 text-rose-800 border-rose-200' : 'bg-emerald-50 text-emerald-800 border-emerald-200'}">
                  {sourceStatusMsgs[cam.camera_id].text}
                </div>
              {/if}
            </div>
          {/if}

          <!-- Per-Camera Inline Zone Calibration Toolbar -->
          {#if isCalibratingThis}
            <div class="p-3 bg-amber-50/80 border-t border-amber-200 flex flex-col gap-2.5 font-mono text-xs">
              <div class="flex items-center justify-between flex-wrap gap-2 pb-1.5 border-b border-amber-200">
                <div class="flex items-center gap-2">
                  <span class="font-bold text-amber-950 uppercase">Zone Calibrator: [{cam.camera_id}]</span>
                  <span class="text-2xs text-amber-800">Drag vertices directly on stream canvas</span>
                </div>

                <div class="flex items-center gap-2">
                  <button 
                    type="button" 
                    class="px-2.5 py-1 bg-white border border-slate-200 hover:bg-slate-100 text-slate-800 font-semibold rounded cursor-pointer"
                    onclick={() => addZoneForCamera(cam.camera_id)}
                  >
                    + Add Zone
                  </button>
                  <button 
                    type="button" 
                    class="px-2.5 py-1 bg-white border border-slate-200 hover:bg-slate-100 text-slate-600 rounded cursor-pointer"
                    onclick={cancelCalibration}
                  >
                    Cancel
                  </button>
                  <button 
                    type="button" 
                    class="px-3.5 py-1 bg-sky-600 hover:bg-sky-700 text-white font-semibold rounded cursor-pointer shadow-2xs disabled:opacity-50"
                    onclick={() => saveCalibration(cam.camera_id)}
                    disabled={isSavingZones}
                  >
                    {isSavingZones ? 'Saving to config.yaml...' : 'Save Zones to config.yaml'}
                  </button>
                </div>
              </div>

              <!-- Zone Editor Fields for Selected Zone -->
              {#if zones[selectedZoneIdx] && (zones[selectedZoneIdx].camera_id || "cam_primary") === cam.camera_id}
                <div class="grid grid-cols-1 sm:grid-cols-4 gap-2 bg-white p-2.5 rounded border border-amber-200">
                  <div class="flex flex-col gap-1">
                    <label for="zone-select-pill" class="text-2xs uppercase text-slate-500 font-semibold">Active Zone</label>
                    <select
                      id="zone-select-pill"
                      bind:value={selectedZoneIdx}
                      class="px-2 py-1 bg-slate-50 border border-slate-200 rounded text-xs font-mono font-semibold"
                    >
                      {#each zones as z, idx}
                        {#if (z.camera_id || "cam_primary") === cam.camera_id}
                          <option value={idx}>{z.label || z.zone_id} ({z.zone_type})</option>
                        {/if}
                      {/each}
                    </select>
                  </div>

                  <div class="flex flex-col gap-1">
                    <label for="zone-type-input" class="text-2xs uppercase text-slate-500 font-semibold">Zone Type</label>
                    <select 
                      id="zone-type-input" 
                      bind:value={zones[selectedZoneIdx].zone_type} 
                      class="px-2 py-1 bg-slate-50 border border-slate-200 rounded text-xs font-mono"
                    >
                      <option value="entry_exit">entry_exit (Footfall)</option>
                      <option value="shelf">shelf (Inventory & SKU)</option>
                      <option value="checkout">checkout (Queue)</option>
                      <option value="product_display">product_display (Dwell)</option>
                    </select>
                  </div>

                  <div class="flex flex-col gap-1">
                    <label for="zone-label-input" class="text-2xs uppercase text-slate-500 font-semibold">Zone Label</label>
                    <input 
                      id="zone-label-input"
                      type="text" 
                      bind:value={zones[selectedZoneIdx].label} 
                      placeholder="e.g. Snacks Shelf"
                      class="px-2 py-1 bg-slate-50 border border-slate-200 rounded text-xs font-mono"
                    />
                  </div>

                  <div class="flex items-end justify-between gap-2">
                    <div class="flex flex-col gap-1 flex-1">
                      <label for="zone-id-input" class="text-2xs uppercase text-slate-500 font-semibold">Zone ID</label>
                      <input 
                        id="zone-id-input"
                        type="text" 
                        bind:value={zones[selectedZoneIdx].zone_id} 
                        class="px-2 py-1 bg-slate-50 border border-slate-200 rounded text-xs font-mono"
                      />
                    </div>
                    <button 
                      type="button" 
                      class="px-2.5 py-1 bg-rose-50 border border-rose-200 hover:bg-rose-100 text-rose-800 rounded font-semibold cursor-pointer shrink-0"
                      onclick={() => removeZone(selectedZoneIdx)}
                      title="Delete this zone"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              {:else}
                <div class="p-2 text-center text-amber-800 bg-amber-100/50 rounded border border-amber-200 text-2xs">
                  No zones configured on [{cam.camera_id}]. Click "+ Add Zone" above to draw an ROI polygon.
                </div>
              {/if}

              {#if zoneStatusMsg}
                <div class="px-2.5 py-1 text-2xs rounded border {isZoneError ? 'bg-rose-50 text-rose-800 border-rose-200' : 'bg-emerald-50 text-emerald-800 border-emerald-200'}">
                  {zoneStatusMsg}
                </div>
              {/if}
            </div>
          {/if}
        </div>
      {/if}
    {/each}

    <!-- Quick Add Stream Tile (if in grid view) -->
    {#if !focusedCamId && !isAddCameraOpen}
      <button
        type="button"
        class="border-2 border-dashed border-slate-200 hover:border-sky-400 bg-slate-50/50 hover:bg-sky-50/30 rounded-lg p-6 flex flex-col items-center justify-center gap-2.5 text-slate-500 hover:text-sky-700 transition-colors cursor-pointer min-h-[220px]"
        onclick={() => isAddCameraOpen = true}
      >
        <div class="w-10 h-10 rounded-full bg-white border border-slate-200 flex items-center justify-center shadow-xs text-sky-600">
          <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="12" y1="5" x2="12" y2="19"/>
            <line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
        </div>
        <div class="text-center font-mono">
          <p class="text-xs font-semibold text-slate-800 uppercase">+ Connect New Camera Stream</p>
          <p class="text-[11px] text-slate-400 font-sans mt-0.5">RTSP CCTV, USB Webcam, or File Feed</p>
        </div>
      </button>
    {/if}
  </div>
</div>
