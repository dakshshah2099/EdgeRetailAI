<script>
  let {
    alerts = [],
    activeFilter = 'open',
    onFilterChange = (status) => {},
    onResolveAlert = (id) => {},
    onResolveAllAlerts = () => {}
  } = $props();

  function formatTimestamp(isoStr) {
    if (!isoStr) return '';
    const date = new Date(isoStr);
    return date.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  }

  const alertTypeBadges = {
    out_of_stock: { label: 'OUT OF STOCK', border: 'border-rose-200', bg: 'bg-rose-50', text: 'text-rose-700' },
    low_stock: { label: 'LOW STOCK', border: 'border-amber-200', bg: 'bg-amber-50', text: 'text-amber-700' },
    queue_congestion: { label: 'QUEUE CONGESTION', border: 'border-amber-200', bg: 'bg-amber-50', text: 'text-amber-700' },
    dwell_anomaly: { label: 'DWELL ANOMALY', border: 'border-sky-200', bg: 'bg-sky-50', text: 'text-sky-700' }
  };

  function parseSKUAlert(message) {
    if (!message) return null;
    const match = message.match(/^(.*?)\s+\((sku_[a-zA-Z0-9_]+)\)\s+on\s+(.*?)\s+is\s+(.*)$/);
    if (!match) return null;
    return {
      name: match[1],
      skuId: match[2],
      shelfId: match[3],
      condition: match[4]
    };
  }

  function getBadge(alert, skuInfo) {
    if (skuInfo) {
      if (alert.severity === 'critical' || skuInfo.condition.includes('out of stock')) {
        return { label: 'SKU DEPLETED', border: 'border-rose-300', bg: 'bg-rose-50', text: 'text-rose-800' };
      }
      return { label: 'SKU LOW STOCK', border: 'border-amber-300', bg: 'bg-amber-50', text: 'text-amber-800' };
    }
    return alertTypeBadges[alert.alert_type] || { label: alert.alert_type, border: 'border-slate-200', bg: 'bg-slate-50', text: 'text-slate-700' };
  }
</script>

<div class="flex flex-col h-full bg-white border border-slate-200 rounded-md shadow-xs">
  <!-- Feed Header -->
  <div class="px-3 sm:px-3.5 py-2 sm:py-2.5 border-b border-slate-200 flex items-center justify-between gap-2 flex-wrap bg-slate-50/50">
    <div class="flex items-center gap-2">
      <span class="text-xs font-bold uppercase tracking-wider text-slate-800">Incident Triage</span>
      <span class="px-1.5 py-0.5 text-xs font-mono bg-white text-slate-600 rounded border border-slate-200">
        {alerts.length}
      </span>
      {#if alerts.some(a => !a.resolved_at)}
        <button 
          type="button"
          class="ml-1 px-2 py-0.5 text-[11px] font-mono rounded bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 cursor-pointer transition-colors"
          onclick={onResolveAllAlerts}
        >
          RESOLVE ALL
        </button>
      {/if}
    </div>

    <!-- Filter Buttons -->
    <div class="flex items-center bg-slate-100 border border-slate-200 rounded-md p-0.5">
      <button 
        type="button"
        class="px-2.5 py-1 text-xs font-mono rounded transition-colors {activeFilter === 'open' ? 'bg-white text-sky-700 shadow-xs font-semibold' : 'text-slate-600 hover:text-slate-900'} cursor-pointer"
        onclick={() => onFilterChange('open')}
      >
        OPEN
      </button>
      <button 
        type="button"
        class="px-2.5 py-1 text-xs font-mono rounded transition-colors {activeFilter === 'resolved' ? 'bg-white text-sky-700 shadow-xs font-semibold' : 'text-slate-600 hover:text-slate-900'} cursor-pointer"
        onclick={() => onFilterChange('resolved')}
      >
        RESOLVED
      </button>
      <button 
        type="button"
        class="px-2.5 py-1 text-xs font-mono rounded transition-colors {activeFilter === 'all' ? 'bg-white text-sky-700 shadow-xs font-semibold' : 'text-slate-600 hover:text-slate-900'} cursor-pointer"
        onclick={() => onFilterChange('all')}
      >
        ALL
      </button>
    </div>
  </div>

  <!-- Incident List -->
  <div class="flex-1 overflow-y-auto p-2.5 space-y-2 min-h-[220px] max-h-[480px]">
    {#if alerts.length === 0}
      <div class="h-full flex flex-col items-center justify-center p-6 text-center text-slate-400 font-mono text-xs">
        <svg class="w-8 h-8 mb-2 text-emerald-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
          <polyline points="22 4 12 14.01 9 11.01"/>
        </svg>
        <span class="text-slate-600 font-medium">NO {activeFilter.toUpperCase()} INCIDENTS</span>
        <span class="text-slate-400 text-xs mt-0.5">All monitored store zones nominal</span>
      </div>
    {:else}
      {#each alerts as alert, idx (alert.alert_id ?? alert.id ?? `${alert.created_at || alert.timestamp || idx}_${alert.zone_id || 'z'}_${idx}`)}
        {@const skuInfo = parseSKUAlert(alert.message)}
        {@const badge = getBadge(alert, skuInfo)}
        <div class="p-2.5 rounded-md border transition-colors bg-white {alert.resolved_at ? 'border-slate-100 opacity-60' : 'border-slate-200 hover:border-slate-300 shadow-xs'}">
          <div class="flex items-center justify-between gap-2 mb-1.5">
            <div class="flex items-center gap-1.5 flex-wrap">
              <span class="px-1.5 py-0.5 text-xs font-mono font-semibold uppercase tracking-wider rounded border {badge.bg} {badge.border} {badge.text}">
                {badge.label}
              </span>
              {#if skuInfo}
                <span class="px-1.5 py-0.5 text-[10px] font-mono bg-sky-50 text-sky-700 border border-sky-200 rounded font-semibold">
                  {skuInfo.skuId}
                </span>
              {/if}
            </div>
            <span class="text-xs font-mono text-slate-400">
              {formatTimestamp(alert.created_at || alert.timestamp)}
            </span>
          </div>

          {#if skuInfo}
            <div class="mb-1.5">
              <div class="text-xs font-bold text-slate-900 leading-snug">
                {skuInfo.name}
              </div>
              <p class="text-xs text-slate-600 font-sans mt-0.5">
                Location: <code class="font-mono text-slate-800 bg-slate-100 px-1 py-0.5 rounded">{skuInfo.shelfId}</code> •
                <strong class="{alert.severity === 'critical' ? 'text-rose-700' : 'text-amber-700'} uppercase">
                  {skuInfo.condition}
                </strong>
              </p>
            </div>
          {:else}
            <p class="text-xs text-slate-700 leading-relaxed font-sans mb-1.5">
              {alert.message}
            </p>
          {/if}

          <div class="flex items-center justify-between text-xs font-mono text-slate-500 pt-1 border-t border-slate-100">
            <span>Zone: <strong class="text-slate-700">{alert.zone_id || 'N/A'}</strong></span>
            {#if alert.resolved_at}
              <span class="text-emerald-600 font-semibold">RESOLVED</span>
            {:else}
              <div class="flex items-center gap-2">
                <span class="text-rose-600 font-semibold animate-pulse">ACTIVE</span>
                <button
                  type="button"
                  class="px-1.5 py-0.5 text-[10px] font-mono rounded bg-slate-100 hover:bg-emerald-50 hover:text-emerald-700 hover:border-emerald-300 border border-slate-200 text-slate-600 cursor-pointer transition-colors"
                  onclick={() => onResolveAlert(alert.alert_id || alert.id)}
                >
                  Resolve ✓
                </button>
              </div>
            {/if}
          </div>
        </div>
      {/each}
    {/if}
  </div>
</div>
