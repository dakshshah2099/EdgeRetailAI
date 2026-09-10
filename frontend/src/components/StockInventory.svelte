<script>
  export let stockEvents = [];

  function formatTime(isoStr) {
    if (!isoStr) return '';
    return new Date(isoStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  function getStatusBadge(status) {
    switch (status) {
      case 'empty':
        return {
          label: 'OUT OF STOCK',
          border: 'border-rose-200',
          bg: 'bg-rose-50/40',
          badge: 'bg-rose-100 text-rose-800 border-rose-200',
          bar: 'bg-rose-500'
        };
      case 'low':
        return {
          label: 'LOW STOCK',
          border: 'border-amber-200',
          bg: 'bg-amber-50/40',
          badge: 'bg-amber-100 text-amber-800 border-amber-200',
          bar: 'bg-amber-500'
        };
      default:
        return {
          label: 'IN STOCK',
          border: 'border-slate-200 hover:border-slate-300',
          bg: 'bg-white',
          badge: 'bg-emerald-100 text-emerald-800 border-emerald-200',
          bar: 'bg-emerald-500'
        };
    }
  }
</script>

<div class="bg-white border border-slate-200 rounded-md p-4 flex flex-col gap-3 shadow-xs">
  <!-- Header -->
  <div class="flex items-center justify-between flex-wrap gap-2 pb-2 border-b border-slate-100">
    <div>
      <div class="flex items-center gap-2">
        <span class="text-sm font-semibold uppercase tracking-wider text-slate-900">Shelf Stock Telemetry</span>
        <span class="px-1.5 py-0.5 text-xs font-mono bg-sky-50 text-sky-700 border border-sky-200 rounded">
          ON-DEVICE CV
        </span>
      </div>
      <p class="text-xs text-slate-500 font-mono mt-0.5">Real-time edge ROI vacancy detection across product shelves.</p>
    </div>
    <span class="text-xs font-mono px-2 py-1 bg-slate-50 border border-slate-200 text-slate-700 rounded">
      MONITORED REGIONS: {stockEvents.length}
    </span>
  </div>

  <!-- Shelf Grid -->
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
    {#if stockEvents.length === 0}
      <div class="col-span-full py-12 text-center text-slate-400 font-mono text-xs">
        NO SHELF STOCK EVENTS RECORDED
      </div>
    {:else}
      {#each stockEvents as shelf (shelf.shelf_id)}
        {@const st = getStatusBadge(shelf.status)}
        <div class="border rounded-md p-3.5 transition-all flex flex-col justify-between gap-3 shadow-xs {st.border} {st.bg}">
          <!-- Top Row -->
          <div class="flex items-center justify-between">
            <span class="font-mono text-xs text-slate-900 font-semibold">
              {shelf.shelf_id}
            </span>
            <span class="px-2 py-0.5 text-xs font-mono uppercase font-semibold border rounded {st.badge}">
              {st.label}
            </span>
          </div>

          <!-- Confidence Meter -->
          <div class="bg-slate-50 border border-slate-200 rounded-md p-2.5 flex flex-col gap-1.5">
            <div class="flex items-center justify-between text-xs font-mono">
              <span class="text-slate-500">Classifier Conf</span>
              <span class="text-slate-800 font-semibold">{Math.round(shelf.confidence * 100)}%</span>
            </div>
            <div class="w-full bg-slate-200 h-1.5 rounded-sm overflow-hidden">
              <div class="h-full rounded-sm {st.bar}" style="width: {Math.round(shelf.confidence * 100)}%;"></div>
            </div>
          </div>

          <!-- Footer -->
          <div class="text-xs font-mono text-slate-400 pt-1 border-t border-slate-100 flex justify-between">
            <span>ROI Model v1</span>
            <span>{formatTime(shelf.timestamp)}</span>
          </div>
        </div>
      {/each}
    {/if}
  </div>
</div>
