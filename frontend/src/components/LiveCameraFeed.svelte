<script>
  import { onMount } from 'svelte';
  import { fetchSystemZones, updateSystemZones } from '../lib/api.js';

  export let isConnected = true;

  let overlayZones = true;
  let overlayDetections = true;
  let targetFps = typeof window !== 'undefined'
    ? parseInt(localStorage.getItem('preferred_stream_fps') || '15', 10) || 15
    : 15;

  $: if (typeof window !== 'undefined' && targetFps) {
    localStorage.setItem('preferred_stream_fps', targetFps.toString());
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
  let activeDragHandle = null; // { zoneIdx, pointIdx }
  let isSavingZones = false;
  let zoneStatusMsg = '';
  let isZoneError = false;

  // Viewport dimensions
  let viewWidth = 640;
  let viewHeight = 480;

  $: streamUrl = `/video/stream?overlay_zones=${!isEditingZones && overlayZones}&overlay_detections=${overlayDetections}&fps=${targetFps}&t=${streamTimestamp}`;

  async function loadZones() {
    try {
      zones = await fetchSystemZones();
    } catch (err) {
      console.error('Failed to load zones:', err);
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
        console.error('Fullscreen request failed:', err);
      });
      isFullscreen = true;
    } else {
      document.exitFullscreen();
      isFullscreen = false;
    }
  }

  function takeSnapshot() {
    const link = document.createElement('a');
    link.href = `/video/snapshot?overlay_zones=${overlayZones}&overlay_detections=${overlayDetections}&t=${Date.now()}`;
    link.download = `retail_snapshot_${new Date().toISOString().replace(/[:.]/g, '-')}.jpg`;
    link.target = '_blank';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  function startZoneEdit() {
    isEditingZones = true;
    zoneStatusMsg = '';
    loadZones();
  }

  function cancelZoneEdit() {
    isEditingZones = false;
    loadZones();
  }

  async function saveZones() {
    isSavingZones = true;
    zoneStatusMsg = '';
    isZoneError = false;
    try {
      zones = await updateSystemZones(zones);
      zoneStatusMsg = '✓ Zone layout saved to config.yaml successfully.';
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
      zone_type: 'shelf',
      label: `New Shelf ${zones.length + 1}`,
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
    if (!activeDragHandle) return;
    const svgRect = e.currentTarget.getBoundingClientRect();
    const scaleX = viewWidth / svgRect.width;
    const scaleY = viewHeight / svgRect.height;

    const curX = Math.round(Math.max(0, Math.min(viewWidth, (e.clientX - svgRect.left) * scaleX)));
    const curY = Math.round(Math.max(0, Math.min(viewHeight, (e.clientY - svgRect.top) * scaleY)));

    const { zoneIdx, ptIdx } = activeDragHandle;
    const nextZones = JSON.parse(JSON.stringify(zones));
    nextZones[zoneIdx].polygon[ptIdx] = [curX, curY];
    zones = nextZones;
  }

  function handleSvgMouseUp() {
    activeDragHandle = null;
  }

  onMount(() => {
    loadZones();
    const handleFsChange = () => {
      isFullscreen = !!document.fullscreenElement;
    };
    document.addEventListener('fullscreenchange', handleFsChange);
    return () => {
      document.removeEventListener('fullscreenchange', handleFsChange);
    };
  });
</script>

<div class="camera-feed-card" bind:this={videoContainer} class:is-fs={isFullscreen}>
  <div class="feed-header">
    <div class="header-left">
      <div class="title-row">
        <h3 class="section-title">Live Edge Camera Stream</h3>
        <span class="live-dot" class:active={isConnected && !isStreamError}></span>
        <span class="status-badge" class:online={isConnected && !isStreamError}>
          {isConnected && !isStreamError ? 'LIVE' : 'STANDBY'}
        </span>
        <span class="model-badge">YOLO26n Active</span>
      </div>
      <p class="section-desc">Real-time inference feed with YOLO person bounding boxes and ROI calibration.</p>
    </div>

    <div class="feed-controls">
      <label class="control-label" title="Toggle Detection Zones Overlay">
        <input type="checkbox" bind:checked={overlayZones} on:change={refreshStream} />
        <span>ROI Zones</span>
      </label>

      <label class="control-label" title="Toggle YOLO26n Person Bounding Boxes">
        <input type="checkbox" bind:checked={overlayDetections} on:change={refreshStream} />
        <span>YOLO Boxes</span>
      </label>

      {#if !isEditingZones}
        <button type="button" class="btn btn-secondary edit-btn" on:click={startZoneEdit}>
          ✏️ Calibrate Zones
        </button>
      {:else}
        <button type="button" class="btn btn-secondary" on:click={addZone} title="Add New Detection Zone">
          + New Zone
        </button>
        <button type="button" class="btn btn-secondary" on:click={cancelZoneEdit}>
          Cancel
        </button>
        <button type="button" class="btn btn-primary" on:click={saveZones} disabled={isSavingZones}>
          {isSavingZones ? 'Saving...' : '💾 Save Zones'}
        </button>
      {/if}

      <div class="fps-group">
        <label for="fps-input">FPS:</label>
        <input 
          id="fps-input"
          type="number" 
          min="1" 
          max="60" 
          step="1"
          class="fps-input"
          bind:value={targetFps} 
          on:change={refreshStream}
          placeholder="15"
        />
      </div>

      <button type="button" class="btn-icon" on:click={takeSnapshot} title="Capture JPEG Snapshot">
        <svg viewBox="0 0 24 24" width="15" height="15" stroke="currentColor" stroke-width="2" fill="none">
          <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
          <circle cx="12" cy="13" r="4"/>
        </svg>
      </button>

      <button type="button" class="btn-icon" on:click={refreshStream} title="Reconnect Video Stream">
        <svg viewBox="0 0 24 24" width="15" height="15" stroke="currentColor" stroke-width="2" fill="none">
          <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
        </svg>
      </button>

      <button type="button" class="btn-icon" on:click={toggleFullscreen} title="Toggle Fullscreen">
        {#if isFullscreen}
          <svg viewBox="0 0 24 24" width="15" height="15" stroke="currentColor" stroke-width="2" fill="none">
            <polyline points="4 14 10 14 10 20"/>
            <polyline points="20 10 14 10 14 4"/>
            <line x1="14" y1="10" x2="21" y2="3"/>
            <line x1="3" y1="21" x2="10" y2="14"/>
          </svg>
        {:else}
          <svg viewBox="0 0 24 24" width="15" height="15" stroke="currentColor" stroke-width="2" fill="none">
            <polyline points="15 3 21 3 21 9"/>
            <polyline points="9 21 3 21 3 15"/>
            <line x1="21" y1="3" x2="14" y2="10"/>
            <line x1="3" y1="21" x2="10" y2="14"/>
          </svg>
        {/if}
      </button>
    </div>
  </div>

  {#if zoneStatusMsg}
    <div class="status-banner" class:banner-error={isZoneError} class:banner-success={!isZoneError}>
      {zoneStatusMsg}
    </div>
  {/if}

  <div class="video-viewport">
    <img 
      src={streamUrl} 
      alt="Edge AI Live Camera Feed" 
      class="stream-img"
      on:load={handleImageLoad}
      on:error={handleImageError}
    />

    <!-- Interactive SVG ROI polygon editor in Calibration mode -->
    {#if isEditingZones}
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <svg 
        class="calibration-svg" 
        viewBox="0 0 {viewWidth} {viewHeight}"
        on:mousemove={handleSvgMouseMove}
        on:mouseup={handleSvgMouseUp}
        on:mouseleave={handleSvgMouseUp}
      >
        {#each zones as zone, zIdx}
          {@const isSel = zIdx === selectedZoneIdx}
          {@const ptsStr = zone.polygon.map((p) => p.join(',')).join(' ')}
          <polygon
            points={ptsStr}
            class="zone-poly type-{zone.zone_type}"
            class:selected-poly={isSel}
            on:mousedown={() => selectedZoneIdx = zIdx}
          />
          <text
            x={zone.polygon[0][0]}
            y={Math.max(20, zone.polygon[0][1] - 10)}
            class="zone-text"
          >
            {zone.label} ({zone.zone_type})
          </text>

          {#if isSel}
            {#each zone.polygon as pt, ptIdx}
              <circle
                cx={pt[0]}
                cy={pt[1]}
                r="7"
                class="drag-handle"
                on:mousedown={(e) => handleSvgMouseDown(zIdx, ptIdx, e)}
              />
            {/each}
          {/if}
        {/each}
      </svg>
    {/if}

    {#if isStreamLoading}
      <div class="video-overlay loading-overlay">
        <span>Initializing camera stream...</span>
      </div>
    {/if}

    <div class="stream-hud">
      <span class="hud-item">MJPEG {targetFps} FPS</span>
      {#if overlayZones}
        <span class="hud-item hud-active">ROI Zones Active</span>
      {/if}
      {#if overlayDetections}
        <span class="hud-item hud-active">YOLO Boxes ON</span>
      {/if}
      <span class="hud-item">Zero PII Stored</span>
    </div>
  </div>

  {#if isEditingZones}
    <div class="zone-editor-bar">
      {#if zones.length > 0 && zones[selectedZoneIdx]}
        <div class="editor-field">
          <label for="zone-select">Zone:</label>
          <select id="zone-select" bind:value={selectedZoneIdx} class="field-select">
            {#each zones as z, i}
              <option value={i}>{z.label || `Zone ${i + 1}`} ({z.zone_type})</option>
            {/each}
          </select>
        </div>

        <div class="editor-field">
          <label for="zone-label-input">Label:</label>
          <input 
            id="zone-label-input"
            type="text" 
            bind:value={zones[selectedZoneIdx].label} 
            class="field-input"
          />
        </div>

        <div class="editor-field">
          <label for="zone-type-select">Type:</label>
          <select id="zone-type-select" bind:value={zones[selectedZoneIdx].zone_type} class="field-select">
            <option value="entry_exit">Entry / Exit</option>
            <option value="shelf">Product Shelf</option>
            <option value="checkout">Checkout Queue</option>
            <option value="product_display">Product Display</option>
          </select>
        </div>

        <div class="editor-field">
          <label for="zone-id-input">ID:</label>
          <input 
            id="zone-id-input"
            type="text" 
            bind:value={zones[selectedZoneIdx].zone_id} 
            class="field-input field-sm"
          />
        </div>

        <button type="button" class="btn btn-secondary" on:click={addZone}>
          + Add New Zone
        </button>

        <button type="button" class="btn btn-danger" on:click={() => removeZone(selectedZoneIdx)}>
          Delete Zone
        </button>
      {:else}
        <div class="empty-zones-bar">
          <span class="empty-zones-msg">No ROI zones configured. Click to create a detection zone:</span>
          <button type="button" class="btn btn-primary" on:click={addZone}>
            + Add New Zone
          </button>
        </div>
      {/if}
    </div>
  {/if}

  <div class="feed-footer">
    <div class="legend-group">
      <span class="legend-item"><span class="color-dot dot-green"></span> Entry/Exit Line</span>
      <span class="legend-item"><span class="color-dot dot-blue"></span> Shelf ROI</span>
      <span class="legend-item"><span class="color-dot dot-amber"></span> Checkout Queue</span>
      <span class="legend-item"><span class="color-dot dot-yolo"></span> YOLO26n BBox</span>
    </div>
    <span class="privacy-notice">Live stream processed purely in-memory on edge hardware</span>
  </div>
</div>

<style>
  .camera-feed-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    box-shadow: var(--shadow-sm);
  }

  .camera-feed-card.is-fs {
    padding: 1rem;
    border-radius: 0;
    width: 100vw;
    height: 100vh;
    background: #0f172a;
    color: #f8fafc;
  }

  .feed-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.75rem;
  }

  .header-left {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .title-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }

  .section-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .is-fs .section-title {
    color: #f8fafc;
  }

  .section-desc {
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .live-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent-red);
  }

  .live-dot.active {
    background: var(--accent-green);
  }

  .status-badge {
    font-size: 0.65rem;
    font-family: var(--font-mono);
    font-weight: 700;
    padding: 0.12rem 0.45rem;
    border-radius: var(--radius-sm);
    background: #f1f5f9;
    color: var(--text-muted);
    border: 1px solid var(--border-color);
  }

  .status-badge.online {
    background: var(--accent-green-light);
    color: var(--accent-green);
    border-color: #a7f3d0;
  }

  .model-badge {
    font-size: 0.65rem;
    font-family: var(--font-mono);
    font-weight: 700;
    padding: 0.12rem 0.45rem;
    border-radius: var(--radius-sm);
    background: var(--accent-purple-light);
    color: var(--accent-purple);
    border: 1px solid #ddd6fe;
  }

  .feed-controls {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .control-label {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.78rem;
    font-weight: 500;
    color: var(--text-secondary);
    cursor: pointer;
    background: var(--bg-primary);
    padding: 0.35rem 0.65rem;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-color);
    user-select: none;
  }

  .control-label input {
    accent-color: var(--accent-blue);
    cursor: pointer;
  }

  .btn {
    padding: 0.35rem 0.75rem;
    border-radius: var(--radius-sm);
    font-size: 0.78rem;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s ease;
  }

  .btn-primary {
    background: var(--accent-blue);
    color: #ffffff;
    border: 1px solid var(--accent-blue);
  }

  .btn-secondary {
    background: #ffffff;
    color: var(--text-secondary);
    border: 1px solid var(--border-color);
  }

  .btn-danger {
    background: var(--accent-red-light);
    color: var(--accent-red);
    border: 1px solid #fecaca;
  }

  .edit-btn {
    background: var(--accent-purple-light);
    color: var(--accent-purple);
    border-color: #ddd6fe;
  }

  .fps-group {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.78rem;
    background: var(--bg-primary);
    padding: 0.3rem 0.6rem;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-color);
  }

  .fps-group label {
    color: var(--text-muted);
    font-weight: 500;
  }

  .fps-input {
    width: 44px;
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 0.15rem 0.35rem;
    font-size: 0.78rem;
    color: var(--text-primary);
    font-weight: 600;
    font-family: var(--font-mono);
    text-align: center;
  }

  .fps-input:focus {
    border-color: var(--border-focus);
    outline: none;
  }

  .btn-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    background: var(--bg-primary);
    color: var(--text-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    transition: all 0.15s ease;
  }

  .btn-icon:hover {
    color: var(--accent-blue);
    border-color: #bfdbfe;
    background: var(--accent-blue-light);
  }

  .status-banner {
    padding: 0.5rem 0.85rem;
    border-radius: var(--radius-sm);
    font-size: 0.8rem;
  }

  .banner-success {
    background: var(--accent-green-light);
    color: var(--accent-green);
    border: 1px solid #a7f3d0;
  }

  .banner-error {
    background: var(--accent-red-light);
    color: var(--accent-red);
    border: 1px solid #fecaca;
  }

  .video-viewport {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    max-height: 540px;
    background: #0f172a;
    border-radius: var(--radius-md);
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--border-color);
  }

  .is-fs .video-viewport {
    max-height: calc(100vh - 120px);
    aspect-ratio: auto;
    height: 100%;
  }

  .stream-img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    display: block;
  }

  .calibration-svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    cursor: default;
  }

  .zone-poly {
    fill-opacity: 0.25;
    stroke-width: 2px;
    cursor: pointer;
  }

  .zone-poly.type-entry_exit { fill: #22c55e; stroke: #22c55e; }
  .zone-poly.type-shelf { fill: #06b6d4; stroke: #06b6d4; }
  .zone-poly.type-checkout { fill: #f59e0b; stroke: #f59e0b; }
  .zone-poly.type-product_display { fill: #a855f7; stroke: #a855f7; }

  .selected-poly {
    stroke-width: 3px;
    stroke-dasharray: 4 2;
    fill-opacity: 0.4;
  }

  .zone-text {
    font-size: 14px;
    font-family: var(--font-mono);
    fill: #ffffff;
    font-weight: 600;
    paint-order: stroke;
    stroke: #0f172a;
    stroke-width: 3px;
  }

  .drag-handle {
    fill: #ffffff;
    stroke: #2563eb;
    stroke-width: 3px;
    cursor: move;
    transition: r 0.15s ease;
  }

  .drag-handle:hover {
    r: 9px;
    fill: #3b82f6;
  }

  .video-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(15, 23, 42, 0.7);
    color: #f8fafc;
    font-size: 0.88rem;
    font-weight: 500;
  }

  .stream-hud {
    position: absolute;
    bottom: 10px;
    left: 10px;
    display: flex;
    gap: 0.4rem;
    pointer-events: none;
  }

  .hud-item {
    font-size: 0.7rem;
    font-family: var(--font-mono);
    padding: 0.15rem 0.45rem;
    border-radius: 4px;
    background: rgba(15, 23, 42, 0.75);
    color: #cbd5e1;
    border: 1px solid rgba(255, 255, 255, 0.1);
  }

  .hud-active {
    color: #34d399;
    border-color: rgba(52, 211, 153, 0.4);
  }

  .zone-editor-bar {
    display: flex;
    align-items: center;
    gap: 1rem;
    background: #f8fafc;
    border: 1px solid var(--border-color);
    padding: 0.75rem 1rem;
    border-radius: var(--radius-sm);
    flex-wrap: wrap;
  }

  .editor-field {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.8rem;
  }

  .editor-field label {
    color: var(--text-muted);
    font-weight: 500;
  }

  .field-input, .field-select {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 0.3rem 0.6rem;
    font-size: 0.8rem;
    color: var(--text-primary);
    outline: none;
  }

  .field-input:focus, .field-select:focus {
    border-color: var(--border-focus);
  }

  .field-sm {
    width: 110px;
    font-family: var(--font-mono);
  }

  .empty-zones-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    gap: 1rem;
    padding: 0.25rem 0;
  }

  .empty-zones-msg {
    font-size: 0.85rem;
    color: var(--text-secondary);
    font-weight: 500;
  }

  .feed-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.75rem;
    font-size: 0.75rem;
    color: var(--text-muted);
    padding-top: 0.25rem;
  }

  .legend-group {
    display: flex;
    align-items: center;
    gap: 1.25rem;
    flex-wrap: wrap;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    color: var(--text-secondary);
    font-weight: 500;
  }

  .color-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }

  .dot-green { background: var(--accent-green); }
  .dot-blue { background: var(--accent-cyan); }
  .dot-amber { background: var(--accent-amber); }
  .dot-yolo { background: #00ff80; }

  .privacy-notice {
    font-style: italic;
    font-size: 0.72rem;
  }
</style>
