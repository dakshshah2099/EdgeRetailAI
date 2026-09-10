<script>
  import { updateSystemEnv } from '../lib/api.js';

  export let envVariables = {};
  export let onSave = () => {};

  let editVars = {};
  let isDirty = false;
  let isSaving = false;
  let statusMessage = '';
  let isError = false;
  let newKey = '';
  let newVal = '';
  let showPassword = false;

  // Only sync from server when user does not have active unsaved edits
  $: if (!isDirty && envVariables) {
    editVars = { ...envVariables };
  }

  function handleInputChange(key, val) {
    editVars = { ...editVars, [key]: val };
    isDirty = true;
    statusMessage = '';
  }

  function setPreset(key, val) {
    editVars = { ...editVars, [key]: val };
    isDirty = true;
    statusMessage = '';
  }

  function resetEdits() {
    editVars = { ...envVariables };
    isDirty = false;
    statusMessage = 'Unsaved changes reset to current server state.';
    isError = false;
  }

  async function handleSave() {
    isSaving = true;
    statusMessage = '';
    isError = false;
    try {
      const res = await updateSystemEnv(editVars);
      statusMessage = 'Settings saved and synced to .env successfully.';
      isError = false;
      isDirty = false;
      onSave(res);
    } catch (err) {
      statusMessage = `Error: ${err.message}`;
      isError = true;
    } finally {
      isSaving = false;
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
</script>

<div class="bg-white border border-slate-200 rounded-md p-3 sm:p-5 flex flex-col gap-4 sm:gap-5 shadow-xs">
  <!-- Panel Header -->
  <div class="flex items-center justify-between flex-wrap gap-2.5 pb-3 border-b border-slate-100">
    <div class="flex flex-col gap-1">
      <div class="flex items-center gap-2.5">
        <h3 class="text-base font-semibold text-slate-900">System Settings</h3>
        {#if isDirty}
          <span class="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-300">
            Unsaved changes
          </span>
        {/if}
      </div>
      <p class="text-xs text-slate-500 font-mono">Direct real-time control over YOLO detection thresholds, RTSP authentication, and system environment variables.</p>
    </div>

    <div class="flex items-center gap-2">
      {#if isDirty}
        <button 
          type="button"
          class="px-3 py-1.5 text-xs font-medium rounded-md bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 cursor-pointer transition-colors disabled:opacity-50"
          on:click={resetEdits} 
          disabled={isSaving}
        >
          Discard
        </button>
      {/if}
      <button 
        type="button"
        class="px-3 py-1.5 text-xs font-medium rounded-md bg-sky-600 hover:bg-sky-700 text-white cursor-pointer transition-colors shadow-xs disabled:opacity-50"
        on:click={handleSave} 
        disabled={isSaving}
      >
        {isSaving ? 'Saving...' : 'Save to .env'}
      </button>
    </div>
  </div>

  {#if statusMessage}
    <div class="px-3 py-2 text-xs font-mono rounded-md border {isError ? 'bg-rose-50 border-rose-200 text-rose-800' : 'bg-emerald-50 border-emerald-200 text-emerald-800'}">
      {statusMessage}
    </div>
  {/if}

  <!-- Quick Threshold Tuning Sliders -->
  <div class="flex flex-col gap-3 p-3 sm:p-4 bg-slate-50 border border-slate-200 rounded-md">
    <h4 class="text-xs font-mono font-semibold uppercase tracking-wider text-slate-700">Detection & Analytics Hyperparameters</h4>
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      <div class="bg-white border border-slate-200 rounded-md p-3 flex flex-col gap-2 shadow-xs">
        <div class="flex items-center justify-between text-xs font-mono text-slate-600">
          <span>YOLO Confidence Threshold</span>
          <strong class="text-sky-700">{editVars['DETECTION_CONFIDENCE_THRESHOLD'] || '0.50'}</strong>
        </div>
        <input 
          type="range" 
          min="0.10" 
          max="0.95" 
          step="0.05"
          value={editVars['DETECTION_CONFIDENCE_THRESHOLD'] || '0.50'}
          on:input={(e) => handleInputChange('DETECTION_CONFIDENCE_THRESHOLD', e.target.value)}
          class="w-full accent-sky-600 cursor-pointer"
        />
      </div>

      <div class="bg-white border border-slate-200 rounded-md p-3 flex flex-col gap-2 shadow-xs">
        <div class="flex items-center justify-between text-xs font-mono text-slate-600">
          <span>Low Stock Threshold</span>
          <strong class="text-sky-700">{editVars['LOW_STOCK_CONFIDENCE_THRESHOLD'] || '0.60'}</strong>
        </div>
        <input 
          type="range" 
          min="0.10" 
          max="0.95" 
          step="0.05"
          value={editVars['LOW_STOCK_CONFIDENCE_THRESHOLD'] || '0.60'}
          on:input={(e) => handleInputChange('LOW_STOCK_CONFIDENCE_THRESHOLD', e.target.value)}
          class="w-full accent-sky-600 cursor-pointer"
        />
      </div>

      <div class="bg-white border border-slate-200 rounded-md p-3 flex flex-col gap-2 shadow-xs sm:col-span-2 lg:col-span-1">
        <div class="flex items-center justify-between text-xs font-mono text-slate-600">
          <span>Queue Congestion Length</span>
          <strong class="text-sky-700">{editVars['QUEUE_CONGESTION_LENGTH'] || '4'} persons</strong>
        </div>
        <input 
          type="range" 
          min="1" 
          max="15" 
          step="1"
          value={editVars['QUEUE_CONGESTION_LENGTH'] || '4'}
          on:input={(e) => handleInputChange('QUEUE_CONGESTION_LENGTH', e.target.value)}
          class="w-full accent-sky-600 cursor-pointer"
        />
      </div>
    </div>
  </div>

  <!-- RTSP Authentication Section -->
  <div class="flex flex-col gap-3 p-3 sm:p-4 bg-slate-50 border border-slate-200 rounded-md">
    <h4 class="text-xs font-mono font-semibold uppercase tracking-wider text-slate-700">RTSP Camera Authentication</h4>
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <div class="flex flex-col gap-1 text-xs font-mono">
        <label for="rtsp-user-input" class="text-slate-600 font-medium">RTSP Username:</label>
        <input 
          id="rtsp-user-input"
          type="text" 
          class="bg-white border border-slate-300 rounded-md px-2.5 py-1.5 text-xs font-mono text-slate-900 focus:outline-none focus:border-sky-500" 
          placeholder="admin" 
          value={editVars['RTSP_USERNAME'] || ''}
          on:input={(e) => handleInputChange('RTSP_USERNAME', e.target.value)}
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
            on:input={(e) => handleInputChange('RTSP_PASSWORD', e.target.value)}
          />
          <button 
            type="button" 
            class="absolute right-2 text-xs font-mono text-slate-500 hover:text-slate-800 cursor-pointer" 
            on:click={() => showPassword = !showPassword}
            title={showPassword ? 'Hide password' : 'Show password'}
          >
            {showPassword ? 'HIDE' : 'SHOW'}
          </button>
        </div>
      </div>
    </div>
    <p class="text-xs text-slate-500 font-mono">Leave blank for streams without password. Credentials are automatically encoded and injected into <code>CAMERA_SOURCE</code> during connection only when password is provided.</p>
  </div>

  <!-- Camera Preset Shortcuts -->
  <div class="flex items-center gap-2 p-2.5 sm:p-3 bg-slate-50 border border-slate-200 rounded-md flex-wrap text-xs font-mono">
    <span class="text-slate-600 font-medium">Camera Feed Presets:</span>
    <div class="flex items-center gap-2 flex-wrap">
      <button 
        type="button"
        class="px-2.5 py-1 bg-white border border-slate-200 hover:border-slate-300 hover:bg-slate-100 text-slate-700 hover:text-slate-900 rounded-md transition-colors cursor-pointer" 
        on:click={() => setPreset('CAMERA_SOURCE', 'rtsp://192.168.1.100:8080/h264_pcm.sdp')}
      >
        Phone RTSP
      </button>
      <button 
        type="button"
        class="px-2.5 py-1 bg-white border border-slate-200 hover:border-slate-300 hover:bg-slate-100 text-slate-700 hover:text-slate-900 rounded-md transition-colors cursor-pointer" 
        on:click={() => setPreset('CAMERA_SOURCE', '0')}
      >
        Webcam (0)
      </button>
      <button 
        type="button"
        class="px-2.5 py-1 bg-white border border-slate-200 hover:border-slate-300 hover:bg-slate-100 text-slate-700 hover:text-slate-900 rounded-md transition-colors cursor-pointer" 
        on:click={() => setPreset('CAMERA_SOURCE', 'tests/fixtures/demo_store_walkthrough.mp4')}
      >
        Demo Video
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

    {#each Object.entries(editVars) as [key, val] (key)}
      <div class="flex flex-col sm:flex-row sm:items-center gap-1.5 sm:gap-3 bg-white p-2 sm:p-2.5 border border-slate-200 rounded-md hover:bg-slate-50/60 transition-colors shadow-xs">
        <div class="flex items-center justify-between sm:w-64 sm:shrink-0">
          <span class="text-xs font-mono font-medium text-slate-900 truncate" title={key}>{key}</span>
          <button 
            type="button"
            class="sm:hidden text-slate-500 hover:text-rose-700 p-1 cursor-pointer" 
            title="Delete variable" 
            on:click={() => removeVariable(key)}
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
            on:input={(e) => handleInputChange(key, e.target.value)}
            placeholder="Value..."
          />
        </div>
        <div class="hidden sm:flex w-10 justify-center">
          <button 
            type="button"
            class="text-slate-500 hover:text-rose-700 p-1 rounded hover:bg-slate-100 transition-colors cursor-pointer" 
            title="Delete variable" 
            on:click={() => removeVariable(key)}
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
          placeholder="NEW_VAR_NAME" 
          bind:value={newKey}
          on:keydown={(e) => e.key === 'Enter' && addVariable()}
        />
      </div>
      <div class="flex-1">
        <input 
          type="text" 
          class="w-full bg-white border border-slate-300 rounded-md px-2.5 py-1 text-xs font-mono text-slate-900 focus:outline-none focus:border-sky-500" 
          placeholder="Value..." 
          bind:value={newVal}
          on:keydown={(e) => e.key === 'Enter' && addVariable()}
        />
      </div>
      <div class="flex sm:w-10 justify-end sm:justify-center">
        <button 
          type="button" 
          class="px-3 py-1 bg-white border border-slate-200 text-slate-700 hover:text-slate-900 hover:bg-slate-100 rounded-md text-xs font-medium cursor-pointer transition-colors disabled:opacity-50" 
          on:click={addVariable} 
          disabled={!newKey.trim()}
        >
          Add
        </button>
      </div>
    </div>
  </div>
</div>
