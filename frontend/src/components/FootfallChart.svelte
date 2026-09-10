<script>
  export let footfallData = null;
  export let groupBy = 'hour';
  export let onGroupByChange = (val) => {};

  function formatBucketTime(isoStr) {
    if (!isoStr) return '';
    const date = new Date(isoStr);
    if (groupBy === 'day') {
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function getMaxBucketCount(buckets) {
    if (!buckets || !buckets.length) return 1;
    let maxVal = 0;
    for (const b of buckets) {
      if (b.enters > maxVal) maxVal = b.enters;
      if (b.exits > maxVal) maxVal = b.exits;
    }
    return maxVal === 0 ? 1 : maxVal;
  }
</script>

<div class="bg-white border border-slate-200 rounded-md p-3 sm:p-4 flex flex-col gap-2.5 sm:gap-3 shadow-xs">
  <!-- Header -->
  <div class="flex items-center justify-between flex-wrap gap-2 pb-2 border-b border-slate-100">
    <div>
      <div class="flex items-center gap-2">
        <span class="text-sm font-semibold uppercase tracking-wider text-slate-900">Footfall Traffic Analytics</span>
        <span class="px-1.5 py-0.5 text-xs font-mono bg-sky-50 text-sky-700 border border-sky-200 rounded">
          BYTE-TRACK
        </span>
      </div>
      <p class="text-xs text-slate-500 font-mono mt-0.5">Temporal customer movement, directional lines, and net store occupancy.</p>
    </div>

    <!-- Aggregation Toggle -->
    <div class="flex items-center bg-slate-100 border border-slate-200 rounded-md p-0.5">
      <button 
        type="button"
        class="px-2.5 py-1 text-xs font-mono rounded transition-colors {groupBy === 'none' ? 'bg-white text-sky-700 shadow-xs font-semibold' : 'text-slate-600 hover:text-slate-900'}"
        on:click={() => onGroupByChange('none')}
      >
        SUMMARY
      </button>
      <button 
        type="button"
        class="px-2.5 py-1 text-xs font-mono rounded transition-colors {groupBy === 'hour' ? 'bg-white text-sky-700 shadow-xs font-semibold' : 'text-slate-600 hover:text-slate-900'}"
        on:click={() => onGroupByChange('hour')}
      >
        HOURLY
      </button>
      <button 
        type="button"
        class="px-2.5 py-1 text-xs font-mono rounded transition-colors {groupBy === 'day' ? 'bg-white text-sky-700 shadow-xs font-semibold' : 'text-slate-600 hover:text-slate-900'}"
        on:click={() => onGroupByChange('day')}
      >
        DAILY
      </button>
    </div>
  </div>

  {#if !footfallData}
    <div class="py-16 text-center text-slate-400 font-mono text-xs">
      NO FOOTFALL TELEMETRY AVAILABLE
    </div>
  {:else}
    <!-- Summary Metrics Grid -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-2.5">
      <div class="bg-slate-50 border border-slate-200 rounded-md p-2.5 sm:p-3">
        <span class="block text-xs font-mono uppercase text-slate-500">Total Ingress</span>
        <span class="text-xl font-mono font-semibold text-emerald-700">+{footfallData.total_enters}</span>
      </div>
      <div class="bg-slate-50 border border-slate-200 rounded-md p-2.5 sm:p-3">
        <span class="block text-xs font-mono uppercase text-slate-500">Total Egress</span>
        <span class="text-xl font-mono font-semibold text-rose-700">-{footfallData.total_exits}</span>
      </div>
      <div class="bg-slate-50 border border-slate-200 rounded-md p-2.5 sm:p-3">
        <span class="block text-xs font-mono uppercase text-slate-500">Net Occupancy</span>
        <span class="text-xl font-mono font-semibold text-sky-700">{footfallData.net_occupancy}</span>
      </div>
      <div class="bg-slate-50 border border-slate-200 rounded-md p-2.5 sm:p-3">
        <span class="block text-xs font-mono uppercase text-slate-500">Time Window</span>
        <span class="text-xs font-mono text-slate-700 truncate block mt-1">
          {#if footfallData.since}
            Since {new Date(footfallData.since).toLocaleTimeString()}
          {:else}
            All-Time Accumulation
          {/if}
        </span>
      </div>
    </div>

    <!-- Bucket Bars Chart -->
    {#if footfallData.buckets && footfallData.buckets.length > 0}
      {@const maxCount = getMaxBucketCount(footfallData.buckets)}
      <div class="bg-slate-50 border border-slate-200 rounded-md p-3 sm:p-3.5 flex flex-col gap-3">
        <div class="flex items-center justify-between flex-wrap gap-2 text-xs font-mono text-slate-600">
          <span>Directional Traffic Flow Distribution</span>
          <div class="flex items-center gap-3">
            <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-sm bg-emerald-600"></span> Ingress (Enters)</span>
            <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-sm bg-rose-600"></span> Egress (Exits)</span>
          </div>
        </div>

        <div class="flex items-end gap-1.5 sm:gap-2 h-44 pt-4 border-b border-slate-200 overflow-x-auto touch-pan-x">
          {#each footfallData.buckets as bucket}
            <div class="flex-1 min-w-[28px] max-w-[48px] h-full flex flex-col justify-end items-center gap-1 group relative">
              <div class="w-full flex items-end justify-center gap-0.5 h-full">
                <!-- Enters Bar -->
                <div 
                  class="w-1/2 bg-emerald-500 hover:bg-emerald-600 transition-all rounded-t-sm"
                  style="height: {Math.max(4, (bucket.enters / maxCount) * 100)}%;"
                  title="Enters: {bucket.enters}"
                ></div>
                <!-- Exits Bar -->
                <div 
                  class="w-1/2 bg-rose-500 hover:bg-rose-600 transition-all rounded-t-sm"
                  style="height: {Math.max(4, (bucket.exits / maxCount) * 100)}%;"
                  title="Exits: {bucket.exits}"
                ></div>
              </div>
              <span class="text-xs font-mono text-slate-500 transform -rotate-45 origin-top-left mt-1 whitespace-nowrap">
                {formatBucketTime(bucket.bucket)}
              </span>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  {/if}
</div>
