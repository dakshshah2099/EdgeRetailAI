<script>
  import { updateSystemEnv, toggleDebugMode } from '../lib/api.js';

  export let debugMode = false;
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
      statusMessage = 'Environment variables saved and synced to .env successfully.';
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

  async function handleToggleDebug() {
    isSaving = true;
    statusMessage = '';
    try {
      const res = await toggleDebugMode();
      debugMode = res.debug_mode;
      editVars = { ...res.variables };
      isDirty = false;
      statusMessage = `Debug Mode switched ${debugMode ? 'ON' : 'OFF'}`;
      isError = false;
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

<div class="debug-panel">
  <div class="panel-header">
    <div class="header-left">
      <div class="title-row">
        <h3>System Environment & Debug Console</h3>
        <span class="status-badge" class:active={debugMode}>
          {debugMode ? 'Debug Active' : 'Debug Inactive'}
        </span>
        {#if isDirty}
          <span class="unsaved-badge">Unsaved changes</span>
        {/if}
      </div>
      <p class="subtitle">Direct real-time control over YOLO26 detection thresholds, RTSP authentication, and <code>.env</code> variables.</p>
    </div>

    <div class="header-actions">
      {#if isDirty}
        <button class="btn btn-secondary" on:click={resetEdits} disabled={isSaving}>
          Discard
        </button>
      {/if}
      <button class="btn btn-secondary" class:active-toggle={debugMode} on:click={handleToggleDebug} disabled={isSaving}>
        {debugMode ? 'Disable Debug Mode' : 'Enable Debug Mode'}
      </button>
      <button class="btn btn-primary" on:click={handleSave} disabled={isSaving || !debugMode}>
        {isSaving ? 'Saving...' : 'Save to .env'}
      </button>
    </div>
  </div>

  {#if statusMessage}
    <div class="status-banner" class:banner-error={isError} class:banner-success={!isError}>
      {statusMessage}
    </div>
  {/if}

  {#if !debugMode}
    <div class="disabled-notice">
      <h4>Debug Mode is Disabled</h4>
      <p>Click "Enable Debug Mode" to modify runtime environment variables, authentication, and detection thresholds.</p>
    </div>
  {:else}
    <!-- Quick Threshold Tuning Sliders -->
    <div class="tuning-section">
      <h4 class="tuning-title">🎯 Detection & Analytics Hyperparameters</h4>
      <div class="sliders-grid">
        <div class="slider-card">
          <div class="slider-header">
            <span>YOLO Confidence Threshold</span>
            <strong>{editVars['DETECTION_CONFIDENCE_THRESHOLD'] || '0.50'}</strong>
          </div>
          <input 
            type="range" 
            min="0.10" 
            max="0.95" 
            step="0.05"
            value={editVars['DETECTION_CONFIDENCE_THRESHOLD'] || '0.50'}
            on:input={(e) => handleInputChange('DETECTION_CONFIDENCE_THRESHOLD', e.target.value)}
            class="range-slider"
          />
        </div>

        <div class="slider-card">
          <div class="slider-header">
            <span>Low Stock Threshold</span>
            <strong>{editVars['LOW_STOCK_CONFIDENCE_THRESHOLD'] || '0.60'}</strong>
          </div>
          <input 
            type="range" 
            min="0.10" 
            max="0.95" 
            step="0.05"
            value={editVars['LOW_STOCK_CONFIDENCE_THRESHOLD'] || '0.60'}
            on:input={(e) => handleInputChange('LOW_STOCK_CONFIDENCE_THRESHOLD', e.target.value)}
            class="range-slider"
          />
        </div>

        <div class="slider-card">
          <div class="slider-header">
            <span>Queue Congestion Length</span>
            <strong>{editVars['QUEUE_CONGESTION_LENGTH'] || '4'} persons</strong>
          </div>
          <input 
            type="range" 
            min="1" 
            max="15" 
            step="1"
            value={editVars['QUEUE_CONGESTION_LENGTH'] || '4'}
            on:input={(e) => handleInputChange('QUEUE_CONGESTION_LENGTH', e.target.value)}
            class="range-slider"
          />
        </div>
      </div>
    </div>

    <!-- RTSP Authentication Section -->
    <div class="auth-section">
      <h4 class="tuning-title">🔐 RTSP Camera Authentication</h4>
      <div class="auth-grid">
        <div class="auth-field">
          <label for="rtsp-user-input">RTSP Username:</label>
          <input 
            id="rtsp-user-input"
            type="text" 
            class="auth-input" 
            placeholder="admin" 
            value={editVars['RTSP_USERNAME'] || ''}
            on:input={(e) => handleInputChange('RTSP_USERNAME', e.target.value)}
          />
        </div>

        <div class="auth-field">
          <label for="rtsp-pass-input">RTSP Password:</label>
          <div class="password-wrapper">
            <input 
              id="rtsp-pass-input"
              type={showPassword ? 'text' : 'password'} 
              class="auth-input pass-input" 
              placeholder="••••••••" 
              value={editVars['RTSP_PASSWORD'] || ''}
              on:input={(e) => handleInputChange('RTSP_PASSWORD', e.target.value)}
            />
            <button 
              type="button" 
              class="eye-btn" 
              on:click={() => showPassword = !showPassword}
              title={showPassword ? 'Hide password' : 'Show password'}
            >
              {showPassword ? '👁️' : '👁️‍🗨️'}
            </button>
          </div>
        </div>
      </div>
      <p class="auth-hint">Credentials are automatically encoded and injected into <code>CAMERA_SOURCE</code> during connection.</p>
    </div>

    <!-- Camera Preset Shortcuts -->
    <div class="preset-section">
      <span class="preset-label">Camera Feed Presets:</span>
      <div class="preset-buttons">
        <button 
          type="button"
          class="preset-btn" 
          on:click={() => setPreset('CAMERA_SOURCE', 'rtsp://192.168.1.100:8080/h264_pcm.sdp')}
        >
          Phone RTSP
        </button>
        <button 
          type="button"
          class="preset-btn" 
          on:click={() => setPreset('CAMERA_SOURCE', '0')}
        >
          Webcam (0)
        </button>
        <button 
          type="button"
          class="preset-btn" 
          on:click={() => setPreset('CAMERA_SOURCE', 'tests/fixtures/demo_store_walkthrough.mp4')}
        >
          Demo Video
        </button>
      </div>
    </div>

    <!-- Env Vars Editor Grid -->
    <div class="env-table">
      <div class="table-header">
        <span class="th-key">Variable Name</span>
        <span class="th-val">Value</span>
        <span class="th-action">Action</span>
      </div>

      {#each Object.entries(editVars) as [key, val] (key)}
        <div class="env-row">
          <div class="key-col">
            <span class="env-key">{key}</span>
          </div>
          <div class="val-col">
            <input 
              type={key === 'RTSP_PASSWORD' && !showPassword ? 'password' : 'text'} 
              class="env-input" 
              value={val}
              on:input={(e) => handleInputChange(key, e.target.value)}
              placeholder="Value..."
            />
          </div>
          <div class="action-col">
            <button 
              type="button"
              class="delete-btn" 
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
      <div class="add-row">
        <div class="key-col">
          <input 
            type="text" 
            class="new-key-input" 
            placeholder="NEW_VAR_NAME" 
            bind:value={newKey}
            on:keydown={(e) => e.key === 'Enter' && addVariable()}
          />
        </div>
        <div class="val-col">
          <input 
            type="text" 
            class="new-val-input" 
            placeholder="Value..." 
            bind:value={newVal}
            on:keydown={(e) => e.key === 'Enter' && addVariable()}
          />
        </div>
        <div class="action-col">
          <button type="button" class="btn btn-secondary add-btn" on:click={addVariable} disabled={!newKey.trim()}>
            Add
          </button>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .debug-panel {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    box-shadow: var(--shadow-sm);
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 1rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--border-color);
  }

  .header-left {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .title-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .title-row h3 {
    font-size: 1.15rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .status-badge {
    font-size: 0.7rem;
    font-family: var(--font-mono);
    font-weight: 600;
    padding: 0.15rem 0.5rem;
    border-radius: var(--radius-sm);
    background: #f1f5f9;
    color: var(--text-muted);
    border: 1px solid var(--border-color);
  }

  .status-badge.active {
    background: var(--accent-purple-light);
    color: var(--accent-purple);
    border-color: #ddd6fe;
  }

  .unsaved-badge {
    font-size: 0.7rem;
    font-family: var(--font-mono);
    font-weight: 600;
    padding: 0.15rem 0.5rem;
    border-radius: var(--radius-sm);
    background: var(--accent-amber-light);
    color: var(--accent-amber);
    border: 1px solid #fde68a;
  }

  .subtitle {
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .subtitle code {
    font-family: var(--font-mono);
    background: #f1f5f9;
    padding: 0.1rem 0.35rem;
    border-radius: 3px;
    color: var(--text-secondary);
    border: 1px solid #e2e8f0;
  }

  .header-actions {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }

  .btn {
    padding: 0.45rem 0.9rem;
    border-radius: var(--radius-sm);
    font-size: 0.8rem;
    font-weight: 500;
    transition: all 0.15s ease;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .btn-primary {
    background: var(--accent-blue);
    color: #ffffff;
    border: 1px solid var(--accent-blue);
  }

  .btn-primary:hover:not(:disabled) {
    background: #1d4ed8;
  }

  .btn-secondary {
    background: #ffffff;
    color: var(--text-secondary);
    border: 1px solid var(--border-color);
  }

  .btn-secondary:hover:not(:disabled) {
    background: #f8fafc;
    color: var(--text-primary);
  }

  .btn-secondary.active-toggle {
    background: var(--accent-purple-light);
    color: var(--accent-purple);
    border-color: #ddd6fe;
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .status-banner {
    padding: 0.6rem 1rem;
    border-radius: var(--radius-sm);
    font-size: 0.85rem;
  }

  .banner-success {
    background: var(--accent-green-light);
    border: 1px solid #a7f3d0;
    color: var(--accent-green);
  }

  .banner-error {
    background: var(--accent-red-light);
    border: 1px solid #fecaca;
    color: var(--accent-red);
  }

  .disabled-notice {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3rem 1rem;
    background: #f8fafc;
    border: 1px dashed var(--border-color);
    border-radius: var(--radius-md);
    gap: 0.5rem;
    text-align: center;
  }

  .disabled-notice h4 {
    color: var(--text-primary);
    font-size: 1rem;
    font-weight: 600;
  }

  .disabled-notice p {
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  .tuning-section, .auth-section {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    padding: 1rem;
    background: #f8fafc;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
  }

  .tuning-title {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .sliders-grid, .auth-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 1rem;
  }

  .slider-card {
    background: #ffffff;
    border: 1px solid var(--border-color);
    padding: 0.75rem 1rem;
    border-radius: var(--radius-sm);
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .slider-header {
    display: flex;
    justify-content: space-between;
    font-size: 0.78rem;
    color: var(--text-secondary);
  }

  .slider-header strong {
    font-family: var(--font-mono);
    color: var(--accent-blue);
  }

  .range-slider {
    width: 100%;
    accent-color: var(--accent-blue);
    cursor: pointer;
  }

  .auth-field {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    font-size: 0.8rem;
  }

  .auth-field label {
    color: var(--text-secondary);
    font-weight: 500;
  }

  .auth-input {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 0.4rem 0.65rem;
    font-size: 0.82rem;
    color: var(--text-primary);
    font-family: var(--font-mono);
    outline: none;
  }

  .auth-input:focus {
    border-color: var(--border-focus);
  }

  .password-wrapper {
    position: relative;
    display: flex;
    align-items: center;
  }

  .pass-input {
    width: 100%;
    padding-right: 2.2rem;
  }

  .eye-btn {
    position: absolute;
    right: 6px;
    font-size: 0.85rem;
    padding: 0.2rem;
    background: none;
    border: none;
    cursor: pointer;
  }

  .auth-hint {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .auth-hint code {
    font-family: var(--font-mono);
    background: #ffffff;
    padding: 0.1rem 0.3rem;
    border-radius: 3px;
    border: 1px solid #cbd5e1;
  }

  .preset-section {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    background: #f8fafc;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    flex-wrap: wrap;
  }

  .preset-label {
    font-size: 0.8rem;
    color: var(--text-secondary);
    font-weight: 500;
  }

  .preset-buttons {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .preset-btn {
    font-size: 0.75rem;
    padding: 0.3rem 0.65rem;
    background: #ffffff;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    transition: all 0.15s ease;
  }

  .preset-btn:hover {
    background: var(--accent-blue-light);
    border-color: #bfdbfe;
    color: var(--accent-blue);
  }

  .env-table {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }

  .table-header {
    display: flex;
    padding: 0.4rem 0.8rem;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    gap: 0.75rem;
  }

  .th-key { width: 260px; flex-shrink: 0; }
  .th-val { flex: 1; }
  .th-action { width: 44px; text-align: center; }

  .env-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    background: #ffffff;
    padding: 0.4rem 0.8rem;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-color);
  }

  .env-row:hover {
    background: #f8fafc;
  }

  .key-col {
    width: 260px;
    flex-shrink: 0;
  }

  .env-key {
    font-family: var(--font-mono);
    font-size: 0.8rem;
    font-weight: 500;
    color: var(--text-primary);
  }

  .val-col {
    flex: 1;
  }

  .action-col {
    width: 44px;
    display: flex;
    justify-content: center;
  }

  .env-input {
    width: 100%;
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 0.35rem 0.6rem;
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: 0.8rem;
    outline: none;
    transition: border-color 0.15s ease;
  }

  .env-input:focus {
    border-color: var(--border-focus);
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
  }

  .delete-btn {
    color: var(--text-muted);
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    transition: all 0.15s ease;
  }

  .delete-btn:hover {
    color: var(--accent-red);
    background: var(--accent-red-light);
  }

  .add-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.5rem 0.8rem;
    background: #f8fafc;
    border: 1px dashed #cbd5e1;
    border-radius: var(--radius-sm);
    margin-top: 0.5rem;
  }

  .new-key-input {
    width: 260px;
    flex-shrink: 0;
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 0.35rem 0.6rem;
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: 0.8rem;
    outline: none;
  }

  .new-key-input:focus {
    border-color: var(--border-focus);
  }

  .new-val-input {
    flex: 1;
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 0.35rem 0.6rem;
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: 0.8rem;
    outline: none;
  }

  .new-val-input:focus {
    border-color: var(--border-focus);
  }

  .add-btn {
    padding: 0.35rem 0.75rem;
    font-size: 0.75rem;
  }
</style>
