<script>
  let {
    staffData = null,
    isLoading = false,
    onRefresh = () => {}
  } = $props();

  let cu = $derived(staffData?.counter_utilization);
  let ar = $derived(staffData?.alert_response);
</script>

<div class="bg-white border border-slate-200 rounded-lg p-4 sm:p-6 shadow-xs flex flex-col gap-5">
  <div class="flex items-center justify-between flex-wrap gap-2 pb-3 border-b border-slate-100">
    <div>
      <h3 class="text-base font-semibold text-slate-900">Staff Efficiency & Intervention</h3>
      <p class="text-xs text-slate-500 font-mono mt-0.5">
        Zero-PII aggregated store-level operational metrics & counter utilization
      </p>
    </div>

    <button
      type="button"
      class="px-3 py-1.5 text-xs font-medium rounded-md bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 cursor-pointer transition-colors disabled:opacity-50"
      onclick={onRefresh}
      disabled={isLoading}
    >
      {isLoading ? "Refreshing..." : "Refresh Staff Metrics"}
    </button>
  </div>

  {#if !staffData}
    <div class="py-12 flex flex-col items-center justify-center text-center">
      <div class="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-slate-400 mb-2">
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
          <circle cx="9" cy="7" r="4"/>
          <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
          <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
        </svg>
      </div>
      <p class="text-xs font-mono text-slate-500">No staff efficiency metrics recorded in this window.</p>
    </div>
  {:else}
    <!-- Counter Utilization Section -->
    <div class="flex flex-col gap-3">
      <h4 class="text-xs font-mono font-semibold text-slate-500 uppercase tracking-wider">
        Checkout Counter Utilization
      </h4>
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div class="bg-slate-50 border border-slate-200 rounded p-3 flex flex-col">
          <span class="text-[11px] font-mono text-slate-500 uppercase">Active Counters</span>
          <strong class="text-xl font-bold text-slate-800">{cu?.counters_active ?? 0}</strong>
        </div>
        <div class="bg-slate-50 border border-slate-200 rounded p-3 flex flex-col">
          <span class="text-[11px] font-mono text-slate-500 uppercase">Opening Alerts</span>
          <strong class="text-xl font-bold text-slate-800">{cu?.counters_recommended ?? 0}</strong>
        </div>
        <div class="bg-slate-50 border border-slate-200 rounded p-3 flex flex-col">
          <span class="text-[11px] font-mono text-slate-500 uppercase">Followed Recommendations</span>
          <strong class="text-xl font-bold text-slate-800">{cu?.recommendations_followed ?? 0}</strong>
        </div>
        <div class="bg-sky-50/70 border border-sky-200 rounded p-3 flex flex-col">
          <span class="text-[11px] font-mono text-sky-700 uppercase">Follow Rate</span>
          <strong class="text-xl font-bold text-sky-800">
            {Math.round((cu?.recommendation_follow_rate ?? 0) * 100)}%
          </strong>
        </div>
      </div>
    </div>

    <!-- Alert Response Section -->
    <div class="flex flex-col gap-3">
      <h4 class="text-xs font-mono font-semibold text-slate-500 uppercase tracking-wider">
        Operational Alert Resolution Speeds
      </h4>
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div class="bg-slate-50 border border-slate-200 rounded p-3 flex flex-col">
          <span class="text-[11px] font-mono text-slate-500 uppercase">Total Resolved</span>
          <strong class="text-xl font-bold text-slate-800">{ar?.total_resolved ?? 0}</strong>
        </div>
        <div class="bg-slate-50 border border-slate-200 rounded p-3 flex flex-col">
          <span class="text-[11px] font-mono text-slate-500 uppercase">Avg Response Time</span>
          <strong class="text-xl font-bold text-slate-800">
            {ar?.avg_response_time_sec != null ? `${ar.avg_response_time_sec.toFixed(1)}s` : "N/A"}
          </strong>
        </div>
        <div class="bg-slate-50 border border-slate-200 rounded p-3 flex flex-col">
          <span class="text-[11px] font-mono text-slate-500 uppercase">Fastest Response</span>
          <strong class="text-xl font-bold text-emerald-700">
            {ar?.min_response_time_sec != null ? `${ar.min_response_time_sec.toFixed(1)}s` : "N/A"}
          </strong>
        </div>
        <div class="bg-slate-50 border border-slate-200 rounded p-3 flex flex-col">
          <span class="text-[11px] font-mono text-slate-500 uppercase">Slowest Response</span>
          <strong class="text-xl font-bold text-amber-700">
            {ar?.max_response_time_sec != null ? `${ar.max_response_time_sec.toFixed(1)}s` : "N/A"}
          </strong>
        </div>
      </div>
    </div>
  {/if}
</div>
