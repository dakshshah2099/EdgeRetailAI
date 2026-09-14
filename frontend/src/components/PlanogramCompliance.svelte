<script>
  let {
    planogramData = null,
    shelfZones = [],
    selectedShelfId = "",
    isLoading = false,
    onSelectShelf = () => {},
    onRefresh = () => {}
  } = $props();

  let complianceRatio = $derived(
    planogramData ? Math.round(planogramData.compliance_ratio * 100) : 0
  );

  let currentZoneId = $derived(
    selectedShelfId || (planogramData ? planogramData.zone_id : (shelfZones[0]?.zone_id || ""))
  );

  function getStatusColor(status) {
    if (status === "ok") return "bg-emerald-500 text-white border-emerald-600";
    if (status === "low") return "bg-amber-400 text-slate-900 border-amber-500";
    return "bg-rose-500 text-white border-rose-600";
  }
</script>

<div class="bg-white border border-slate-200 rounded-lg p-4 sm:p-6 shadow-xs flex flex-col gap-4">
  <div class="flex items-center justify-between flex-wrap gap-2 pb-3 border-b border-slate-100">
    <div>
      <div class="flex items-center gap-2">
        <h3 class="text-base font-semibold text-slate-900">Planogram Compliance</h3>
        {#if planogramData}
          <span class="px-2 py-0.5 text-xs font-mono font-semibold rounded {complianceRatio >= 80 ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-amber-50 text-amber-700 border border-amber-200'}">
            {complianceRatio}% COMPLIANT
          </span>
        {/if}
      </div>
      <div class="flex items-center gap-2 text-xs font-mono mt-1">
        <span class="text-slate-500">Target Shelf:</span>
        {#if shelfZones.length > 0}
          <select
            class="bg-slate-50 border border-slate-200 rounded px-2 py-0.5 text-xs font-mono text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-500 cursor-pointer"
            value={currentZoneId}
            onchange={(e) => onSelectShelf(e.target.value)}
          >
            {#each shelfZones as shelf (shelf.zone_id)}
              <option value={shelf.zone_id}>{shelf.label || shelf.zone_id} ({shelf.zone_id})</option>
            {/each}
          </select>
        {:else}
          <span class="font-semibold text-slate-700">{currentZoneId || "None configured"}</span>
        {/if}
      </div>
    </div>

    <button
      type="button"
      class="px-3 py-1.5 text-xs font-medium rounded-md bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 cursor-pointer transition-colors disabled:opacity-50"
      onclick={onRefresh}
      disabled={isLoading}
    >
      {isLoading ? "Checking..." : "Refresh Facing Grid"}
    </button>
  </div>

  {#if !planogramData}
    <div class="py-12 flex flex-col items-center justify-center text-center">
      <div class="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-slate-400 mb-2">
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
          <line x1="3" y1="9" x2="21" y2="9"/>
          <line x1="9" y1="21" x2="9" y2="9"/>
        </svg>
      </div>
      <p class="text-xs font-mono text-slate-500">No planogram data loaded yet for shelf zone.</p>
    </div>
  {:else}
    <!-- Summary KPI cards -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
      <div class="bg-slate-50 border border-slate-200 rounded p-2.5 flex flex-col">
        <span class="text-[11px] font-mono text-slate-500 uppercase">Total Facings</span>
        <strong class="text-lg font-bold text-slate-800">{planogramData.total_facings}</strong>
      </div>
      <div class="bg-slate-50 border border-slate-200 rounded p-2.5 flex flex-col">
        <span class="text-[11px] font-mono text-slate-500 uppercase">Expected Active</span>
        <strong class="text-lg font-bold text-slate-800">{planogramData.expected_nonempty}</strong>
      </div>
      <div class="bg-emerald-50/70 border border-emerald-200 rounded p-2.5 flex flex-col">
        <span class="text-[11px] font-mono text-emerald-700 uppercase">Stocked Facings</span>
        <strong class="text-lg font-bold text-emerald-800">{planogramData.actual_nonempty}</strong>
      </div>
      <div class="bg-rose-50/70 border border-rose-200 rounded p-2.5 flex flex-col">
        <span class="text-[11px] font-mono text-rose-700 uppercase">Missing / Low</span>
        <strong class="text-lg font-bold text-rose-800">{planogramData.missing_facings.length}</strong>
      </div>
    </div>

    <!-- Interactive Facing Grid Visualization -->
    <div class="flex flex-col gap-2">
      <div class="flex items-center justify-between text-xs font-mono text-slate-500">
        <span>SHELF FACING LAYOUT MATRIX</span>
        <div class="flex items-center gap-3">
          <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded bg-emerald-500"></span> OK</span>
          <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded bg-amber-400"></span> LOW</span>
          <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded bg-rose-500"></span> EMPTY</span>
        </div>
      </div>

      <div class="p-4 bg-slate-100/70 border border-slate-200 rounded-md">
        <div class="grid gap-2" style="grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));">
          {#each planogramData.facing_statuses as facing (`${facing.facing_index[0]}_${facing.facing_index[1]}`)}
            <div class="flex flex-col items-center justify-center p-3 rounded border {getStatusColor(facing.status)} shadow-xs text-center transition-transform hover:scale-102">
              <span class="text-[10px] font-mono opacity-80">R{facing.facing_index[0]}C{facing.facing_index[1]}</span>
              <strong class="text-xs font-bold uppercase tracking-wider">{facing.status}</strong>
              <span class="text-[9px] font-mono opacity-75">{Math.round(facing.confidence * 100)}%</span>
            </div>
          {/each}
        </div>
      </div>
    </div>
  {/if}
</div>
