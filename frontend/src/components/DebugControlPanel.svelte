<script>
  import { onMount } from 'svelte';
  import { 
    updateSystemEnv, 
    resetTelemetry, 
    resolveAllAlerts, 
    fetchVideoStatus, 
    fetchCameras,
    registerCamera,
    unregisterCamera
  } from '../lib/api.js';

  let {
    envVariables = {},
    cameraStatus = null,
    onSave = () => {},
    onCameraSourceUpdated = () => {}
  } = $props();

  // Video and Mesh Status State
  let liveVideoStatus = $state(null);
  let meshCameras = $state([]);
  let isLoadingCameras = $state(false);

  // Mesh Camera Registration
  let isAddMeshOpen = $state(false);
  let newCamId = $state('');
  let newCamSource = $state('');
  let newCamRole = $state('general');
  let newCamLabel = $state('');
  let meshErrorMsg = $state('');
  let isRegisteringMesh = $state(false);

  // System & Operations State
  let isResettingTelemetry = $state(false);
  let isResolvingAlerts = $state(false);
  let isSavingEnv = $state(false);
  let statusMessage = $state('');
  let isError = $state(false);

  // Env Vars Editor State
  let editVars = $state({});
  let isDirty = $state(false);
  let newKey = $state('');
  let newVal = $state('');
  let showPassword = $state(false);
  let envFilter = $state('');

  // Sync incoming envVariables if user hasn't made unsaved edits
  $effect(() => {
    if (!isDirty && envVariables && Object.keys(envVariables).length > 0) {
      editVars = { ...envVariables };
    }
  });

  // Sync incoming cameraStatus from parent if available
  $effect(() => {
    if (cameraStatus) {
      liveVideoStatus = cameraStatus;
    }
  });

  onMount(async () => {
    await refreshCameraDetails();
  });

  async function refreshCameraDetails() {
    isLoadingCameras = true;
    try {
      const [statRes, meshRes] = await Promise.allSettled([
        fetchVideoStatus(),
        fetchCameras()
      ]);

      if (statRes.status === 'fulfilled') {
        liveVideoStatus = statRes.value;
      }

      if (meshRes.status === 'fulfilled' && meshRes.value?.cameras) {
        meshCameras = meshRes.value.cameras;
      }
    } catch (err) {
      console.warn('Failed to refresh camera configuration details:', err);
    } finally {
      isLoadingCameras = false;
    }
  }

  async function handleRegisterMeshCamera(e) {
    if (e) e.preventDefault();
    if (!newCamId.trim() || !newCamSource.trim()) {
      meshErrorMsg = 'Camera ID and Source are required.';
      return;
    }

    isRegisteringMesh = true;
    meshErrorMsg = '';
    try {
      await registerCamera({
        camera_id: newCamId.trim().toLowerCase().replace(/[^a-z0-9_]/g, '_'),
        source: newCamSource.trim(),
        role: newCamRole,
        label: newCamLabel.trim() || newCamId.trim(),
      });
      newCamId = '';
      newCamSource = '';
      newCamLabel = '';
      isAddMeshOpen = false;
      await refreshCameraDetails();
      onCameraSourceUpdated();
    } catch (err) {
      meshErrorMsg = `Failed to register camera: ${err.message}`;
    } finally {
      isRegisteringMesh = false;
    }
  }

  async function handleRemoveMeshCamera(cameraId) {
    if (!confirm(`Are you sure you want to remove camera node "${cameraId}" from mesh?`)) return;
    try {
      await unregisterCamera(cameraId);
      await refreshCameraDetails();
      onCameraSourceUpdated();
    } catch (err) {
      alert(`Failed to remove camera: ${err.message}`);
    }
  }

  function handleInputChange(key, val) {
    editVars = { ...editVars, [key]: val };
    isDirty = true;
    statusMessage = '';
  }

  function resetEdits() {
    editVars = { ...envVariables };
    isDirty = false;
    statusMessage = 'Unsaved changes discarded. Synchronized to server state.';
    isError = false;
  }

  async function handleSaveEnv() {
    isSavingEnv = true;
    statusMessage = '';
    isError = false;
    try {
      const res = await updateSystemEnv(editVars);
      statusMessage = '✓ Configuration saved: System environment variables synced to .env.';
      isError = false;
      isDirty = false;
      onSave(res);
      await refreshCameraDetails();
    } catch (err) {
      statusMessage = `Error saving configuration: ${err.message}`;
      isError = true;
    } finally {
      isSavingEnv = false;
    }
  }

  function addVariable() {
    if (!newKey.trim()) return;
    const cleanKey = newKey.trim().toUpperCase().replace(/[^A-Z0-9_]/g, '_');
    editVars = { ...editVars, [cleanKey]: newVal.trim() };
    isDirty = true;
    newKey = '';
    newVal = '';
  }

  function removeVariable(key) {
    const next = { ...editVars };
    delete next[key];
    editVars = next;
    isDirty = true;
  }

  async function handleResetTelemetry() {
    if (isResettingTelemetry) return;
    if (!confirm('Are you sure you want to purge all store telemetry? This deletes all detection events, dwell events, queue records, stock depletions, alerts, and audit logs.')) {
      return;
    }

    isResettingTelemetry = true;
    try {
      const res = await resetTelemetry();
      statusMessage = `✓ Telemetry purged: ${res.cleared_events || 0} events reset to zero. Store database clean.`;
      isError = false;
      onCameraSourceUpdated();
    } catch (err) {
      statusMessage = `Error purging telemetry: ${err.message}`;
      isError = true;
    } finally {
      isResettingTelemetry = false;
    }
  }

  async function handleResolveAllAlerts() {
    if (isResolvingAlerts) return;
    isResolvingAlerts = true;
    try {
      const res = await resolveAllAlerts();
      statusMessage = `✓ Operations triage: ${res.resolved_count || 0} operational alerts marked resolved.`;
      isError = false;
      onCameraSourceUpdated();
    } catch (err) {
      statusMessage = `Error resolving alerts: ${err.message}`;
      isError = true;
    } finally {
      isResolvingAlerts = false;
    }
  }

  let filteredEnvVars = $derived(
    Object.entries(editVars).filter(([k]) => 
      !envFilter.trim() || k.toLowerCase().includes(envFilter.toLowerCase())
    )
  );
</script>

<div class="flex flex-col gap-4 sm:gap-5 pb-8">
  <!-- Top Page Header -->
  <div class="bg-white border border-slate-200 rounded-md p-3 sm:p-5 flex flex-col gap-3 shadow-xs">
    <div class="flex items-center justify-between flex-wrap gap-2.5 pb-3 border-b border-slate-100">
      <div class="flex flex-col gap-1">
        <div class="flex items-center gap-2.5">
          <h2 class="text-base font-semibold text-slate-900">Edge Node Configuration</h2>
          {#if isDirty}
            <span class="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-300">
              Unsaved changes
            </span>
          {/if}
        </div>
        <p class="text-xs text-slate-500 font-mono">
          Direct real-time control over YOLO vision hyperparameters, RTSP authentication, and system environment. Camera sources and detection zones are calibrated in the Calibrate Zones interface.
        </p>
      </div>

      <div class="flex items-center gap-2 flex-wrap">
        <button 
          type="button"
          class="px-2.5 py-1.5 text-xs font-mono font-medium rounded-md bg-white text-rose-700 border border-rose-200 hover:bg-rose-50 cursor-pointer transition-colors disabled:opacity-50"
          onclick={handleResetTelemetry}
          disabled={isResettingTelemetry}
          title="Wipe all transient detection, queue, stock, alert, and audit events from local SQLite database"
        >
          {isResettingTelemetry ? 'Purging...' : 'Purge All Telemetry'}
        </button>

        <button 
          type="button"
          class="px-2.5 py-1.5 text-xs font-mono font-medium rounded-md bg-white text-emerald-700 border border-emerald-200 hover:bg-emerald-50 cursor-pointer transition-colors disabled:opacity-50"
          onclick={handleResolveAllAlerts}
          disabled={isResolvingAlerts}
          title="Resolve all open operational alerts"
        >
          {isResolvingAlerts ? 'Resolving...' : 'Resolve All Alerts'}
        </button>

        {#if isDirty}
          <button 
            type="button"
            class="px-3 py-1.5 text-xs font-medium rounded-md bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 cursor-pointer transition-colors disabled:opacity-50"
            onclick={resetEdits} 
            disabled={isSavingEnv}
          >
            Discard
          </button>
        {/if}

        <button 
          type="button"
          class="px-3 py-1.5 text-xs font-medium rounded-md bg-sky-600 hover:bg-sky-700 text-white cursor-pointer transition-colors shadow-xs disabled:opacity-50"
          onclick={handleSaveEnv} 
          disabled={isSavingEnv}
        >
          {isSavingEnv ? 'Saving...' : 'Save Configuration (.env)'}
        </button>
      </div>
    </div>

    {#if statusMessage}
      <div class="px-3 py-2 text-xs font-mono rounded-md border {isError ? 'bg-rose-50 border-rose-200 text-rose-800' : 'bg-emerald-50 border-emerald-200 text-emerald-800'}">
        {statusMessage}
      </div>
    {/if}
  </div>

  <!-- SECTION 1: RTSP Authentication & Network -->
  <div class="bg-white border border-slate-200 rounded-md p-4 sm:p-5 flex flex-col gap-3 shadow-xs">
    <div class="border-b border-slate-100 pb-2.5">
      <h3 class="text-sm font-semibold uppercase tracking-wider text-slate-900">RTSP Stream Credentials & Network Transport</h3>
      <p class="text-xs text-slate-500 font-mono mt-0.5">Credentials are injected into the RTSP stream URL securely during connection.</p>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
      <div class="flex flex-col gap-1 text-xs font-mono">
        <label for="rtsp-user-input" class="text-slate-600 font-medium">RTSP Username:</label>
        <input 
          id="rtsp-user-input"
          type="text" 
          class="bg-white border border-slate-300 rounded-md px-2.5 py-1.5 text-xs font-mono text-slate-900 focus:outline-none focus:border-sky-500" 
          placeholder="admin" 
          value={editVars['RTSP_USERNAME'] || ''}
          oninput={(e) => handleInputChange('RTSP_USERNAME', e.target.value)}
        />
      </div>

      <div class="flex flex-col gap-1 text-xs font-mono">
        <label for="rtsp-pass-input" class="text-slate-600 font-medium">RTSP Password:</label>
        <div class="relative flex items-center">
          <input 
            id="rtsp-pass-input"
            type={showPassword ? 'text' : 'password'} 
            class="w-full bg-white border border-slate-300 rounded-md px-2.5 py-1.5 pr-12 text-xs font-mono text-slate-900 focus:outline-none focus:border-sky-500" 
            placeholder="••••••••" 
            value={editVars['RTSP_PASSWORD'] || ''}
            oninput={(e) => handleInputChange('RTSP_PASSWORD', e.target.value)}
          />
          <button 
            type="button" 
            class="absolute right-2 text-xs font-mono text-slate-500 hover:text-slate-800 cursor-pointer" 
            onclick={() => showPassword = !showPassword}
            title={showPassword ? 'Hide password' : 'Show password'}
          >
            {showPassword ? 'HIDE' : 'SHOW'}
          </button>
        </div>
      </div>

      <div class="flex flex-col gap-1 text-xs font-mono">
        <label for="rtsp-transport-select" class="text-slate-600 font-medium">Transport Protocol:</label>
        <select
          id="rtsp-transport-select"
          class="bg-white border border-slate-300 rounded-md px-2.5 py-1.5 text-xs font-mono text-slate-900 focus:outline-none focus:border-sky-500 cursor-pointer"
          value={editVars['RTSP_TRANSPORT'] || 'tcp'}
          onchange={(e) => handleInputChange('RTSP_TRANSPORT', e.target.value)}
        >
          <option value="tcp">TCP (Reliable, Recommended)</option>
          <option value="udp">UDP (Low Latency)</option>
        </select>
      </div>
    </div>
  </div>

  <!-- SECTION 2: Vision & Edge Analytics Hyperparameters -->
  <div class="bg-white border border-slate-200 rounded-md p-4 sm:p-5 flex flex-col gap-3 shadow-xs">
    <div class="border-b border-slate-100 pb-2.5">
      <h3 class="text-sm font-semibold uppercase tracking-wider text-slate-900">Detection & Analytics Hyperparameters</h3>
      <p class="text-xs text-slate-500 font-mono mt-0.5">Tuning inference confidence cutoffs, stock replenishment thresholds, and queue triggers.</p>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      <!-- YOLO Detection Confidence -->
      <div class="bg-slate-50 border border-slate-200 rounded-md p-3 flex flex-col gap-2">
        <div class="flex items-center justify-between text-xs font-mono text-slate-600">
          <span>YOLO Confidence Cutoff</span>
          <strong class="text-sky-700 font-semibold">{editVars['DETECTION_CONFIDENCE_THRESHOLD'] || '0.40'}</strong>
        </div>
        <input 
          type="range" 
          min="0.10" 
          max="0.95" 
          step="0.05"
          value={editVars['DETECTION_CONFIDENCE_THRESHOLD'] || '0.40'}
          oninput={(e) => handleInputChange('DETECTION_CONFIDENCE_THRESHOLD', e.target.value)}
          class="w-full accent-sky-600 cursor-pointer"
        />
        <span class="text-2xs font-mono text-slate-400">Min bounding box detection confidence</span>
      </div>

      <!-- Low Stock Threshold -->
      <div class="bg-slate-50 border border-slate-200 rounded-md p-3 flex flex-col gap-2">
        <div class="flex items-center justify-between text-xs font-mono text-slate-600">
          <span>Low Stock Alert Cutoff</span>
          <strong class="text-sky-700 font-semibold">{editVars['LOW_STOCK_CONFIDENCE_THRESHOLD'] || '0.55'}</strong>
        </div>
        <input 
          type="range" 
          min="0.10" 
          max="0.95" 
          step="0.05"
          value={editVars['LOW_STOCK_CONFIDENCE_THRESHOLD'] || '0.55'}
          oninput={(e) => handleInputChange('LOW_STOCK_CONFIDENCE_THRESHOLD', e.target.value)}
          class="w-full accent-sky-600 cursor-pointer"
        />
        <span class="text-2xs font-mono text-slate-400">Triggers shelf replenishment notification</span>
      </div>

      <!-- Queue Congestion Length -->
      <div class="bg-slate-50 border border-slate-200 rounded-md p-3 flex flex-col gap-2 sm:col-span-2 lg:col-span-1">
        <div class="flex items-center justify-between text-xs font-mono text-slate-600">
          <span>Queue Congestion Trigger</span>
          <strong class="text-sky-700 font-semibold">{editVars['QUEUE_CONGESTION_LENGTH'] || '4'} persons</strong>
        </div>
        <input 
          type="range" 
          min="1" 
          max="15" 
          step="1"
          value={editVars['QUEUE_CONGESTION_LENGTH'] || '4'}
          oninput={(e) => handleInputChange('QUEUE_CONGESTION_LENGTH', e.target.value)}
          class="w-full accent-sky-600 cursor-pointer"
        />
        <span class="text-2xs font-mono text-slate-400">Lane customer count threshold</span>
      </div>
    </div>
  </div>

  <!-- SECTION 3: Multi-Camera Mesh Network -->
  <div class="bg-white border border-slate-200 rounded-md p-4 sm:p-5 flex flex-col gap-3 shadow-xs">
    <div class="flex items-center justify-between flex-wrap gap-2 border-b border-slate-100 pb-2.5">
      <div>
        <div class="flex items-center gap-2">
          <h3 class="text-sm font-semibold uppercase tracking-wider text-slate-900">Multi-Camera Mesh Network</h3>
          <span class="px-2 py-0.5 text-xs font-mono bg-sky-50 text-sky-800 border border-sky-200 rounded">
            {meshCameras.length + 1} NODES
          </span>
        </div>
        <p class="text-xs text-slate-500 font-mono mt-0.5">Registered edge cameras analyzing entrance, checkout lanes, and shelf aisles.</p>
      </div>

      <button 
        type="button"
        class="px-2.5 py-1 text-xs font-mono font-medium rounded-md bg-sky-50 text-sky-800 border border-sky-300 hover:bg-sky-100 cursor-pointer transition-colors"
        onclick={() => isAddMeshOpen = !isAddMeshOpen}
      >
        {isAddMeshOpen ? 'Close Form' : '+ Add Camera Node'}
      </button>
    </div>

    <!-- Add Mesh Camera Drawer -->
    {#if isAddMeshOpen}
      <form class="p-3 bg-slate-50 border border-slate-200 rounded-md flex flex-col gap-2.5" onsubmit={handleRegisterMeshCamera}>
        <span class="text-xs font-mono font-semibold uppercase text-slate-800">Register Secondary Camera Node</span>
        <div class="grid grid-cols-1 sm:grid-cols-4 gap-2 text-xs font-mono">
          <div>
            <label for="mesh-cam-id" class="text-slate-600 block mb-1">Camera ID *</label>
            <input 
              id="mesh-cam-id"
              type="text" 
              class="w-full bg-white border border-slate-300 rounded px-2 py-1 text-slate-900 focus:outline-none focus:border-sky-500" 
              placeholder="cam_aisle_2"
              bind:value={newCamId}
              required
            />
          </div>
          <div class="sm:col-span-2">
            <label for="mesh-cam-src" class="text-slate-600 block mb-1">Source URI / Path *</label>
            <input 
              id="mesh-cam-src"
              type="text" 
              class="w-full bg-white border border-slate-300 rounded px-2 py-1 text-slate-900 focus:outline-none focus:border-sky-500" 
              placeholder="rtsp://192.168.1.102:8080/live or 1"
              bind:value={newCamSource}
              required
            />
          </div>
          <div>
            <label for="mesh-cam-role" class="text-slate-600 block mb-1">Role</label>
            <select
              id="mesh-cam-role"
              class="w-full bg-white border border-slate-300 rounded px-2 py-1 text-slate-900 focus:outline-none focus:border-sky-500 cursor-pointer"
              bind:value={newCamRole}
            >
              <option value="entrance">Entrance</option>
              <option value="checkout">Checkout</option>
              <option value="shelf">Shelf</option>
              <option value="general">General</option>
            </select>
          </div>
        </div>

        {#if meshErrorMsg}
          <div class="text-xs font-mono text-rose-700 bg-rose-50 border border-rose-200 p-2 rounded">
            {meshErrorMsg}
          </div>
        {/if}

        <div class="flex justify-end gap-2 pt-1">
          <button 
            type="button" 
            class="px-2.5 py-1 text-xs font-mono rounded border border-slate-300 hover:bg-slate-100 text-slate-700 cursor-pointer"
            onclick={() => isAddMeshOpen = false}
          >
            Cancel
          </button>
          <button 
            type="submit" 
            class="px-3 py-1 text-xs font-mono rounded bg-sky-600 hover:bg-sky-700 text-white font-medium cursor-pointer"
            disabled={isRegisteringMesh}
          >
            {isRegisteringMesh ? 'Registering...' : 'Register Camera'}
          </button>
        </div>
      </form>
    {/if}

    <!-- Cameras List Table -->
    <div class="border border-slate-200 rounded-md overflow-hidden text-xs font-mono">
      <div class="grid grid-cols-12 gap-2 bg-slate-50 p-2 font-semibold text-slate-600 border-b border-slate-200">
        <span class="col-span-3">Camera Node</span>
        <span class="col-span-2">Role</span>
        <span class="col-span-4">Source</span>
        <span class="col-span-2 text-center">Status</span>
        <span class="col-span-1 text-right">Action</span>
      </div>

      <!-- Primary Camera Row -->
      <div class="grid grid-cols-12 gap-2 p-2.5 bg-white border-b border-slate-100 items-center">
        <div class="col-span-3 font-semibold text-slate-900 flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full {liveVideoStatus?.is_connected ? 'bg-emerald-500' : 'bg-slate-400'}"></span>
          <span>cam_primary (Primary)</span>
        </div>
        <div class="col-span-2 text-slate-600 uppercase">primary</div>
        <div class="col-span-4 text-slate-800 truncate" title={liveVideoStatus?.source || '0'}>
          {liveVideoStatus?.source || '0'}
        </div>
        <div class="col-span-2 text-center">
          <span class="px-2 py-0.5 rounded border {liveVideoStatus?.is_connected ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-slate-100 text-slate-600 border-slate-200'}">
            {liveVideoStatus?.is_connected ? 'ONLINE' : 'STANDBY'}
          </span>
        </div>
        <div class="col-span-1 text-right text-slate-400">
          Default
        </div>
      </div>

      <!-- Secondary Mesh Cameras Rows -->
      {#each meshCameras as cam (cam.camera_id)}
        <div class="grid grid-cols-12 gap-2 p-2.5 bg-white border-b border-slate-100 items-center hover:bg-slate-50/50">
          <div class="col-span-3 font-semibold text-slate-900 flex items-center gap-1.5 truncate">
            <span class="w-2 h-2 rounded-full {cam.is_connected ? 'bg-emerald-500' : 'bg-slate-400'}"></span>
            <span>{cam.label || cam.camera_id}</span>
          </div>
          <div class="col-span-2 text-slate-600 uppercase">{cam.role || 'general'}</div>
          <div class="col-span-4 text-slate-800 truncate" title={cam.source}>
            {cam.source}
          </div>
          <div class="col-span-2 text-center">
            <span class="px-2 py-0.5 rounded border {cam.is_connected ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-slate-100 text-slate-600 border-slate-200'}">
              {cam.is_connected ? 'ONLINE' : 'STANDBY'}
            </span>
          </div>
          <div class="col-span-1 text-right">
            <button 
              type="button" 
              class="text-slate-400 hover:text-rose-600 p-1 cursor-pointer transition-colors"
              title="Remove camera from mesh"
              onclick={() => handleRemoveMeshCamera(cam.camera_id)}
            >
              <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none">
                <path d="M18 6L6 18M6 6l12 12"/>
              </svg>
            </button>
          </div>
        </div>
      {/each}
    </div>
  </div>

  <!-- SECTION 4: System Environment Variables (.env) -->
  <div class="bg-white border border-slate-200 rounded-md p-4 sm:p-5 flex flex-col gap-3 shadow-xs">
    <div class="flex items-center justify-between flex-wrap gap-2 border-b border-slate-100 pb-2.5">
      <div>
        <h3 class="text-sm font-semibold uppercase tracking-wider text-slate-900">System Environment Variables</h3>
        <p class="text-xs text-slate-500 font-mono mt-0.5">Direct editor for runtime flags, network ports, and logging levels in <code class="text-slate-800 bg-slate-100 px-1 py-0.5 rounded">.env</code>.</p>
      </div>

      <div class="flex items-center gap-2">
        <input 
          type="text" 
          placeholder="Filter variables..." 
          class="bg-white border border-slate-300 rounded px-2.5 py-1 text-xs font-mono text-slate-800 focus:outline-none focus:border-sky-500 w-44"
          bind:value={envFilter}
        />
        <button 
          type="button"
          class="px-3 py-1 text-xs font-medium rounded-md bg-sky-600 hover:bg-sky-700 text-white cursor-pointer transition-colors shadow-xs disabled:opacity-50"
          onclick={handleSaveEnv} 
          disabled={isSavingEnv}
        >
          {isSavingEnv ? 'Saving...' : 'Save to .env'}
        </button>
      </div>
    </div>

    <!-- Env Vars Editor Table -->
    <div class="flex flex-col gap-1.5">
      <div class="hidden sm:flex items-center gap-3 px-3 py-1.5 text-xs font-mono font-semibold uppercase tracking-wider text-slate-500">
        <span class="w-64 shrink-0">Variable Name</span>
        <span class="flex-1">Value</span>
        <span class="w-10 text-center">Action</span>
      </div>

      {#each filteredEnvVars as [key, val] (key)}
        <div class="flex flex-col sm:flex-row sm:items-center gap-1.5 sm:gap-3 bg-white p-2 sm:p-2.5 border border-slate-200 rounded-md hover:bg-slate-50/60 transition-colors shadow-xs">
          <div class="flex items-center justify-between sm:w-64 sm:shrink-0">
            <span class="text-xs font-mono font-medium text-slate-900 truncate" title={key}>{key}</span>
            <button 
              type="button"
              class="sm:hidden text-slate-500 hover:text-rose-700 p-1 cursor-pointer" 
              title="Delete variable" 
              onclick={() => removeVariable(key)}
            >
              <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none">
                <path d="M18 6L6 18M6 6l12 12"/>
              </svg>
            </button>
          </div>
          <div class="flex-1">
            <input 
              type={key === 'RTSP_PASSWORD' && !showPassword ? 'password' : 'text'} 
              class="w-full bg-white border border-slate-300 rounded-md px-2.5 py-1 text-xs font-mono text-slate-900 focus:outline-none focus:border-sky-500" 
              value={val}
              oninput={(e) => handleInputChange(key, e.target.value)}
              placeholder="Value..."
            />
          </div>
          <div class="hidden sm:flex w-10 justify-center">
            <button 
              type="button"
              class="text-slate-500 hover:text-rose-700 p-1 rounded hover:bg-slate-100 transition-colors cursor-pointer" 
              title="Delete variable" 
              onclick={() => removeVariable(key)}
            >
              <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none">
                <path d="M18 6L6 18M6 6l12 12"/>
              </svg>
            </button>
          </div>
        </div>
      {/each}

      <!-- Add new variable row -->
      <div class="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3 p-2 sm:p-2.5 bg-slate-50 border border-dashed border-slate-300 rounded-md mt-1">
        <div class="sm:w-64 sm:shrink-0">
          <input 
            type="text" 
            class="w-full bg-white border border-slate-300 rounded-md px-2.5 py-1 text-xs font-mono text-slate-900 focus:outline-none focus:border-sky-500" 
            placeholder="NEW_VARIABLE_NAME" 
            bind:value={newKey}
            onkeydown={(e) => e.key === 'Enter' && addVariable()}
          />
        </div>
        <div class="flex-1">
          <input 
            type="text" 
            class="w-full bg-white border border-slate-300 rounded-md px-2.5 py-1 text-xs font-mono text-slate-900 focus:outline-none focus:border-sky-500" 
            placeholder="Value..." 
            bind:value={newVal}
            onkeydown={(e) => e.key === 'Enter' && addVariable()}
          />
        </div>
        <div class="flex sm:w-10 justify-end sm:justify-center">
          <button 
            type="button" 
            class="px-3 py-1 bg-white border border-slate-200 text-slate-700 hover:text-slate-900 hover:bg-slate-100 rounded-md text-xs font-medium cursor-pointer transition-colors disabled:opacity-50" 
            onclick={addVariable} 
            disabled={!newKey.trim()}
          >
            Add
          </button>
        </div>
      </div>
    </div>
  </div>
</div>
