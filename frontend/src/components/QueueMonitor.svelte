<script>
  export let queueEvents = [];
  export let congestionThreshold = 4;

  function formatTime(isoStr) {
    if (!isoStr) return '';
    return new Date(isoStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
</script>

<div class="bg-white border border-slate-200 rounded-md p-3 sm:p-4 flex flex-col gap-2.5 sm:gap-3 shadow-xs">
  <!-- Header -->
  <div class="flex items-center justify-between flex-wrap gap-2 pb-2 border-b border-slate-100">
    <div>
      <div class="flex items-center gap-2">
        <span class="text-sm font-semibold uppercase tracking-wider text-slate-900">Checkout Queue Intelligence</span>
        <span class="px-1.5 py-0.5 text-xs font-mono bg-sky-50 text-sky-700 border border-sky-200 rounded">
          ACTIVE SENSORS
        </span>
      </div>
      <p class="text-xs text-slate-500 font-mono mt-0.5">Real-time checkout lane wait time estimation and congestion mitigation.</p>
    </div>
    <span class="text-xs font-mono px-2 py-1 bg-amber-50 border border-amber-200 text-amber-800 rounded">
      CONGESTION THRESHOLD: ≥ {congestionThreshold} PERSONS
    </span>
  </div>

  <!-- Counters Grid -->
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5 sm:gap-3">
    {#if queueEvents.length === 0}
      <div class="col-span-full py-12 text-center text-slate-400 font-mono text-xs">
        NO CHECKOUT COUNTER TELEMETRY DETECTED
      </div>
    {:else}
      {#each queueEvents as item (item.counter_id)}
        {@const isCongested = item.queue_length >= congestionThreshold}
        {@const isPredCongested = !isCongested && item.predicted_queue_length != null && item.predicted_queue_length >= congestionThreshold}
        <div class="bg-white border rounded-md p-3 sm:p-3.5 transition-all flex flex-col justify-between gap-3 shadow-xs {isCongested ? 'border-rose-300 bg-rose-50/30' : isPredCongested ? 'border-amber-300 bg-amber-50/30' : 'border-slate-200 hover:border-slate-300'}">
          <!-- Top Row -->
          <div class="flex items-center justify-between">
            <span class="font-mono text-xs text-slate-700">
              LANE: <strong class="text-slate-900">{item.counter_id}</strong>
            </span>
            {#if isCongested}
              <span class="px-2 py-0.5 text-xs font-mono uppercase bg-rose-100 text-rose-800 border border-rose-200 rounded font-semibold animate-pulse">
                CONGESTED
              </span>
            {:else if isPredCongested}
              <span class="px-2 py-0.5 text-xs font-mono uppercase bg-amber-100 text-amber-800 border border-amber-200 rounded">
                SURGE PREDICTED
              </span>
            {:else}
              <span class="px-2 py-0.5 text-xs font-mono uppercase bg-emerald-100 text-emerald-800 border border-emerald-200 rounded">
                OPTIMAL
              </span>
            {/if}
          </div>

          <!-- Metrics Row -->
          <div class="grid grid-cols-2 gap-2 bg-slate-50 border border-slate-200 rounded-md p-2.5">
            <div>
              <span class="block text-xs font-mono uppercase text-slate-500">Queue Length</span>
              <span class="text-xl font-mono font-semibold {isCongested ? 'text-rose-700' : 'text-slate-900'}">
                {item.queue_length} <small class="text-xs font-normal text-slate-500">prs</small>
              </span>
            </div>
            <div>
              <span class="block text-xs font-mono uppercase text-slate-500">Est. Wait</span>
              <span class="text-xl font-mono font-semibold {isCongested ? 'text-amber-700' : 'text-sky-700'}">
                {item.avg_wait_est_sec != null ? `${Math.round(item.avg_wait_est_sec)}s` : 'N/A'}
              </span>
            </div>
          </div>

          <!-- Forecast Banner -->
          {#if item.predicted_queue_length != null}
            <div class="px-2 py-1 rounded bg-slate-50 border border-slate-200 flex items-center justify-between text-xs font-mono">
              <span class="text-slate-600">Forecast (+3m):</span>
              <span class="text-sky-800 font-semibold">~{item.predicted_queue_length} prs ({Math.round(item.predicted_wait_sec ?? 0)}s)</span>
            </div>
          {/if}

          <!-- Visual Queue Track -->
          <div class="flex items-center gap-1.5 py-1">
            {#each Array(Math.min(10, Math.max(item.queue_length, 1))) as _, i}
              <span 
                class="flex-1 h-1.5 rounded-sm transition-all {i < item.queue_length ? (isCongested ? 'bg-rose-500' : 'bg-sky-500') : 'bg-slate-200'}"
              ></span>
            {/each}
          </div>

          <div class="text-xs font-mono text-slate-400 pt-1 border-t border-slate-100 flex justify-between">
            <span>Edge Tracker</span>
            <span>{formatTime(item.timestamp)}</span>
          </div>
        </div>
      {/each}
    {/if}
  </div>
</div>
