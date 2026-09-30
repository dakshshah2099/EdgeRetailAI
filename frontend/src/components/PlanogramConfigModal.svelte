<script>
  import { onMount } from 'svelte';
  import { 
    fetchPlanogramLayout, 
    updatePlanogramLayout, 
    fetchSKUCatalog, 
    registerSKU 
  } from '../lib/api.js';

  let {
    isOpen = false,
    zoneId = '',
    shelfZones = [],
    skuCatalog = [],
    onClose = () => {},
    onSaved = () => {}
  } = $props();

  let activeTab = $state('layout'); // 'layout' or 'catalog'
  let targetZoneId = $state('');
  let isLoading = $state(false);
  let isSaving = $state(false);
  let errorMsg = $state('');
  let successMsg = $state('');

  $effect(() => {
    targetZoneId = zoneId || (shelfZones[0]?.zone_id || '');
  });

  // Planogram Grid state
  let gridRows = $state(2);
  let gridCols = $state(3);
  let expectedFacings = $state(new Set()); // Set of "r,c"
  let facingExpectedSkus = $state({}); // { "r,c": sku_id }

  // SKU Catalog Form state
  let newSkuId = $state('');
  let newSkuName = $state('');
  let newSkuBrand = $state('');
  let newSkuCategory = $state('general');
  let newSkuZone = $state('');

  // Selected cell for popup editing
  let selectedCell = $state(null); // { r, c }

  $effect(() => {
    if (zoneId) {
      targetZoneId = zoneId;
    }
  });

  $effect(() => {
    if (isOpen && targetZoneId) {
      loadLayout(targetZoneId);
      newSkuZone = targetZoneId;
    }
  });

  async function loadLayout(zId) {
    if (!zId) return;
    isLoading = true;
    errorMsg = '';
    try {
      const data = await fetchPlanogramLayout(zId);
      gridRows = data.grid_rows || 2;
      gridCols = data.grid_cols || 3;
      expectedFacings = new Set((data.expected_nonempty_facings || []).map(f => `${f[0]},${f[1]}`));
      facingExpectedSkus = { ...(data.facing_expected_skus || {}) };
    } catch (err) {
      console.warn('Could not load planogram layout:', err);
      // Fallback default
      gridRows = 2;
      gridCols = 3;
      const defaults = new Set();
      for (let r = 0; r < 2; r++) {
        for (let c = 0; c < 3; c++) {
          defaults.add(`${r},${c}`);
        }
      }
      expectedFacings = defaults;
      facingExpectedSkus = {};
    } finally {
      isLoading = false;
    }
  }

  function toggleFacingActive(r, c) {
    const key = `${r},${c}`;
    const next = new Set(expectedFacings);
    if (next.has(key)) {
      next.delete(key);
    } else {
      next.add(key);
    }
    expectedFacings = next;
  }

  function handleSelectCellSku(r, c, skuId) {
    const key = `${r},${c}`;
    const updated = { ...facingExpectedSkus };
    if (!skuId) {
      delete updated[key];
    } else {
      updated[key] = skuId;
      // Also ensure it is marked as active
      if (!expectedFacings.has(key)) {
        const next = new Set(expectedFacings);
        next.add(key);
        expectedFacings = next;
      }
    }
    facingExpectedSkus = updated;
  }

  async function handleSaveLayout() {
    isSaving = true;
    errorMsg = '';
    successMsg = '';
    try {
      const expectedArray = Array.from(expectedFacings).map(k => {
        const [r, c] = k.split(',').map(Number);
        return [r, c];
      });

      await updatePlanogramLayout({
        zone_id: targetZoneId,
        grid_rows: Number(gridRows),
        grid_cols: Number(gridCols),
        expected_nonempty_facings: expectedArray,
        facing_expected_skus: facingExpectedSkus
      });

      successMsg = 'Planogram layout saved successfully!';
      onSaved();
      setTimeout(() => {
        if (isOpen) successMsg = '';
      }, 3000);
    } catch (err) {
      errorMsg = err.message || 'Failed to save layout';
    } finally {
      isSaving = false;
    }
  }

  async function handleRegisterSku(e) {
    if (e) e.preventDefault();
    if (!newSkuId.trim() || !newSkuName.trim()) {
      errorMsg = 'SKU ID and Name are required.';
      return;
    }

    isSaving = true;
    errorMsg = '';
    try {
      await registerSKU({
        sku_id: newSkuId.trim(),
        name: newSkuName.trim(),
        brand: newSkuBrand.trim() || 'General',
        category: newSkuCategory.trim() || 'general',
        expected_zone_id: newSkuZone || targetZoneId
      });

      newSkuId = '';
      newSkuName = '';
      newSkuBrand = '';
      successMsg = 'SKU registered in catalog!';
      onSaved();
      setTimeout(() => { successMsg = ''; }, 3000);
    } catch (err) {
      errorMsg = err.message || 'Failed to register SKU';
    } finally {
      isSaving = false;
    }
  }

  function getSkuName(skuId) {
    const found = skuCatalog.find(s => s.sku_id === skuId);
    return found ? found.name : skuId;
  }
</script>

{#if isOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs">
    <div class="bg-white border border-slate-200 rounded-xl shadow-2xl max-w-2xl w-full flex flex-col max-h-[90vh] overflow-hidden animate-in fade-in zoom-in-95 duration-150">
      
      <!-- Modal Header -->
      <div class="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between bg-slate-50/70">
        <div class="flex items-center gap-2">
          <div class="w-7 h-7 rounded bg-sky-100 border border-sky-200 flex items-center justify-center text-sky-700">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
              <line x1="3" y1="9" x2="21" y2="9"/>
              <line x1="9" y1="21" x2="9" y2="9"/>
            </svg>
          </div>
          <div>
            <h3 class="text-sm font-semibold text-slate-900">Planogram & SKU Configuration</h3>
            <p class="text-xs text-slate-500 font-mono">Configure shelf grids and expected product placement</p>
          </div>
        </div>
        <button
          type="button"
          aria-label="Close"
          class="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 cursor-pointer transition-colors"
          onclick={onClose}
        >
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <!-- Tab Switcher & Zone Selector -->
      <div class="px-5 py-2.5 border-b border-slate-200 bg-white flex items-center justify-between flex-wrap gap-2">
        <div class="flex items-center gap-1 bg-slate-100 p-0.5 rounded-lg border border-slate-200 text-xs">
          <button
            type="button"
            class="px-3 py-1 rounded-md font-medium transition-all cursor-pointer {activeTab === 'layout' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'}"
            onclick={() => activeTab = 'layout'}
          >
            Facing Grid Layout
          </button>
          <button
            type="button"
            class="px-3 py-1 rounded-md font-medium transition-all cursor-pointer {activeTab === 'catalog' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'}"
            onclick={() => activeTab = 'catalog'}
          >
            SKU Catalog ({skuCatalog.length})
          </button>
        </div>

        <div class="flex items-center gap-2 text-xs font-mono">
          <span class="text-slate-500">Shelf Zone:</span>
          <select
            class="bg-slate-50 border border-slate-200 rounded px-2 py-1 text-xs font-mono text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-500 cursor-pointer"
            value={targetZoneId}
            onchange={(e) => {
              targetZoneId = e.target.value;
              loadLayout(targetZoneId);
            }}
          >
            {#each shelfZones as shelf (shelf.zone_id)}
              <option value={shelf.zone_id}>{shelf.label || shelf.zone_id}</option>
            {/each}
          </select>
        </div>
      </div>

      <!-- Messages -->
      {#if errorMsg}
        <div class="mx-5 mt-3 p-2.5 bg-rose-50 border border-rose-200 rounded-md text-xs text-rose-700 font-mono">
          {errorMsg}
        </div>
      {/if}
      {#if successMsg}
        <div class="mx-5 mt-3 p-2.5 bg-emerald-50 border border-emerald-200 rounded-md text-xs text-emerald-700 font-mono">
          {successMsg}
        </div>
      {/if}

      <!-- Modal Body -->
      <div class="p-5 flex-1 overflow-y-auto space-y-4">
        {#if activeTab === 'layout'}
          <!-- Grid Dimension Controls -->
          <div class="flex items-center gap-4 bg-slate-50 p-3 rounded-lg border border-slate-200 text-xs">
            <div class="flex items-center gap-2">
              <label for="grid-rows" class="font-medium text-slate-700">Rows:</label>
              <input
                id="grid-rows"
                type="number"
                min="1"
                max="6"
                class="w-14 px-2 py-1 border border-slate-300 rounded font-mono text-center"
                bind:value={gridRows}
              />
            </div>
            <div class="flex items-center gap-2">
              <label for="grid-cols" class="font-medium text-slate-700">Columns:</label>
              <input
                id="grid-cols"
                type="number"
                min="1"
                max="6"
                class="w-14 px-2 py-1 border border-slate-300 rounded font-mono text-center"
                bind:value={gridCols}
              />
            </div>
            <span class="text-slate-400 font-mono">|</span>
            <div class="text-slate-500 font-mono">
              Total Facings: <strong class="text-slate-800">{gridRows * gridCols}</strong>
            </div>
            <div class="text-slate-500 font-mono ml-auto">
              Active: <strong class="text-emerald-700">{expectedFacings.size}</strong>
            </div>
          </div>

          <!-- Helper instructions -->
          <div class="flex items-center justify-between text-[11px] text-slate-500">
            <span>Click slot to toggle Active/Disabled. Use dropdown to assign expected SKU.</span>
            <div class="flex items-center gap-2">
              <span class="inline-block w-2.5 h-2.5 rounded bg-emerald-100 border border-emerald-300"></span> Active
              <span class="inline-block w-2.5 h-2.5 rounded bg-slate-100 border border-slate-300"></span> Disabled
            </div>
          </div>

          <!-- Interactive Planogram Layout Matrix -->
          {#if isLoading}
            <div class="py-12 text-center text-xs text-slate-400 font-mono">Loading shelf layout...</div>
          {:else}
            <div 
              class="grid gap-2 p-3 bg-slate-100/60 border border-slate-200 rounded-lg select-none"
              style="grid-template-columns: repeat({gridCols}, minmax(0, 1fr));"
            >
              {#each Array(Number(gridRows)) as _, r}
                {#each Array(Number(gridCols)) as _, c}
                  {@const key = `${r},${c}`}
                  {@const isActive = expectedFacings.has(key)}
                  {@const assignedSku = facingExpectedSkus[key]}
                  <div class="flex flex-col gap-1.5 p-2 rounded-lg border transition-all {isActive ? 'bg-white border-emerald-400 shadow-xs' : 'bg-slate-200/50 border-slate-300 opacity-60'}">
                    <button
                      type="button"
                      class="flex items-center justify-between w-full cursor-pointer text-left"
                      onclick={() => toggleFacingActive(r, c)}
                    >
                      <span class="text-[10px] font-mono font-semibold text-slate-500">R{r}C{c}</span>
                      <span class="text-[10px] font-mono px-1 py-0.2 rounded {isActive ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-slate-200 text-slate-600'}">
                        {isActive ? 'ACTIVE' : 'OFF'}
                      </span>
                    </button>

                    <!-- SKU Dropdown -->
                    <select
                      class="w-full text-[11px] font-mono bg-slate-50 border border-slate-200 rounded px-1.5 py-1 text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-500 cursor-pointer disabled:opacity-50"
                      value={assignedSku || ''}
                      disabled={!isActive}
                      onchange={(e) => handleSelectCellSku(r, c, e.target.value)}
                    >
                      <option value="">-- No SKU assigned --</option>
                      {#each skuCatalog as item (item.sku_id)}
                        <option value={item.sku_id}>{item.name} ({item.sku_id})</option>
                      {/each}
                    </select>

                    {#if assignedSku}
                      <span class="text-[9px] font-mono text-sky-700 truncate" title={getSkuName(assignedSku)}>
                        {getSkuName(assignedSku)}
                      </span>
                    {/if}
                  </div>
                {/each}
              {/each}
            </div>
          {/if}

        {:else if activeTab === 'catalog'}
          <!-- Register New SKU Form -->
          <form onsubmit={handleRegisterSku} class="bg-slate-50 p-3.5 rounded-lg border border-slate-200 space-y-3">
            <h4 class="text-xs font-semibold text-slate-900 uppercase tracking-wider font-mono">Register New Catalog SKU</h4>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div>
                <label for="new-sku-id" class="block font-medium text-slate-700 mb-1">SKU ID (e.g. sku_cola):</label>
                <input
                  id="new-sku-id"
                  type="text"
                  placeholder="sku_cola"
                  class="w-full px-2.5 py-1.5 border border-slate-300 rounded font-mono text-xs"
                  bind:value={newSkuId}
                  required
                />
              </div>
              <div>
                <label for="new-sku-name" class="block font-medium text-slate-700 mb-1">Display Name:</label>
                <input
                  id="new-sku-name"
                  type="text"
                  placeholder="Coca-Cola 330ml"
                  class="w-full px-2.5 py-1.5 border border-slate-300 rounded text-xs"
                  bind:value={newSkuName}
                  required
                />
              </div>
              <div>
                <label for="new-sku-brand" class="block font-medium text-slate-700 mb-1">Brand:</label>
                <input
                  id="new-sku-brand"
                  type="text"
                  placeholder="Coca-Cola"
                  class="w-full px-2.5 py-1.5 border border-slate-300 rounded text-xs"
                  bind:value={newSkuBrand}
                />
              </div>
              <div>
                <label for="new-sku-zone" class="block font-medium text-slate-700 mb-1">Assigned Shelf:</label>
                <select
                  id="new-sku-zone"
                  class="w-full px-2.5 py-1.5 border border-slate-300 rounded text-xs font-mono"
                  bind:value={newSkuZone}
                >
                  {#each shelfZones as shelf (shelf.zone_id)}
                    <option value={shelf.zone_id}>{shelf.label || shelf.zone_id}</option>
                  {/each}
                </select>
              </div>
            </div>

            <div class="flex justify-end pt-1">
              <button
                type="submit"
                class="px-3 py-1.5 text-xs font-medium rounded-md bg-sky-600 text-white hover:bg-sky-700 cursor-pointer disabled:opacity-50"
                disabled={isSaving}
              >
                {isSaving ? 'Registering...' : '+ Add to Catalog'}
              </button>
            </div>
          </form>

          <!-- Current Catalog List -->
          <div class="border border-slate-200 rounded-lg overflow-hidden">
            <div class="bg-slate-100/70 px-3 py-2 border-b border-slate-200 text-xs font-mono font-semibold text-slate-600">
              Registered Catalog Products ({skuCatalog.length})
            </div>
            {#if skuCatalog.length === 0}
              <div class="p-6 text-center text-xs text-slate-400 font-mono">No SKUs registered yet.</div>
            {:else}
              <div class="divide-y divide-slate-100 max-h-60 overflow-y-auto">
                {#each skuCatalog as item (item.sku_id)}
                  <div class="p-2.5 flex items-center justify-between text-xs hover:bg-slate-50">
                    <div>
                      <div class="font-medium text-slate-900">{item.name}</div>
                      <div class="text-[11px] font-mono text-slate-500">ID: {item.sku_id} &bull; Brand: {item.brand}</div>
                    </div>
                    <span class="px-2 py-0.5 text-[10px] font-mono bg-sky-50 text-sky-700 border border-sky-200 rounded">
                      {item.expected_zone_id || 'unassigned'}
                    </span>
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        {/if}
      </div>

      <!-- Modal Footer -->
      <div class="px-5 py-3 border-t border-slate-200 bg-slate-50/70 flex items-center justify-between">
        <button
          type="button"
          class="px-3.5 py-1.5 text-xs font-medium rounded-md border border-slate-300 text-slate-700 bg-white hover:bg-slate-50 cursor-pointer"
          onclick={onClose}
        >
          Close
        </button>

        {#if activeTab === 'layout'}
          <button
            type="button"
            class="px-4 py-1.5 text-xs font-medium rounded-md bg-emerald-600 text-white hover:bg-emerald-700 cursor-pointer disabled:opacity-50 transition-colors shadow-xs"
            onclick={handleSaveLayout}
            disabled={isSaving}
          >
            {isSaving ? 'Saving...' : 'Save Planogram Layout'}
          </button>
        {/if}
      </div>

    </div>
  </div>
{/if}
