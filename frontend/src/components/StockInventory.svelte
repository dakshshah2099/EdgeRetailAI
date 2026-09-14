<script>
  let {
    stockEvents = [],
    skuReport = null,
    skuCatalog = []
  } = $props();

  function formatTime(isoStr) {
    if (!isoStr) return '';
    return new Date(isoStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  let catalogByZone = $derived(
    Array.isArray(skuCatalog)
      ? Object.fromEntries(skuCatalog.filter(c => c.expected_zone_id).map(c => [c.expected_zone_id, c]))
      : {}
  );

  let skuByShelf = $derived(
    (skuReport && skuReport.items)
      ? Object.fromEntries(skuReport.items.map(item => [item.shelf_id, item]))
      : {}
  );

  function getStatusBadge(status) {
    switch (status) {
      case 'empty':
        return {
          label: 'OUT OF STOCK',
          border: 'border-rose-300',
          bg: 'bg-rose-50/50',
          badge: 'bg-rose-100 text-rose-800 border-rose-200',
          bar: 'bg-rose-500',
          alertText: 'CRITICAL: Immediate shelf restock needed'
        };
      case 'low':
        return {
          label: 'LOW STOCK',
          border: 'border-amber-300',
          bg: 'bg-amber-50/50',
          badge: 'bg-amber-100 text-amber-800 border-amber-200',
          bar: 'bg-amber-500',
          alertText: 'WARNING: Prepare replenishment'
        };
      default:
        return {
          label: 'IN STOCK',
          border: 'border-slate-200 hover:border-slate-300',
          bg: 'bg-white',
          badge: 'bg-emerald-100 text-emerald-800 border-emerald-200',
          bar: 'bg-emerald-500',
          alertText: null
        };
    }
  }

  // Combine shelves from recorded stock events, registered catalog zones, or live detected SKUs
  let allShelfIds = $derived(Array.from(new Set([
    ...stockEvents.map(s => s.shelf_id),
    ...(Array.isArray(skuCatalog) ? skuCatalog.filter(c => c.expected_zone_id).map(c => c.expected_zone_id) : []),
    ...(skuReport && skuReport.items ? skuReport.items.filter(i => i.detected_sku_id || i.facing_count > 0).map(i => i.shelf_id) : [])
  ])));

  let cardsData = $derived(allShelfIds.map(shelfId => {
    const sEv = stockEvents.find(s => s.shelf_id === shelfId);
    const skuItem = skuByShelf[shelfId];
    const catItem = catalogByZone[shelfId];

    const status = (sEv && sEv.status) || (skuItem && skuItem.status === 'misplaced' ? 'ok' : skuItem?.status) || 'ok';
    const confidence = (sEv && sEv.confidence) || skuItem?.confidence || 0.85;
    const timestamp = (sEv && sEv.timestamp) || skuItem?.timestamp;
    const skuName = skuItem?.detected_sku_name || catItem?.name || `Shelf Item (${shelfId})`;
    const skuId = skuItem?.detected_sku_id || skuItem?.expected_sku_id || catItem?.sku_id || `sku_${shelfId}`;
    const brand = catItem?.brand || 'Store';
    const category = catItem?.category || 'General';
    const facingCount = skuItem ? skuItem.facing_count : (status === 'empty' ? 0 : status === 'low' ? 2 : 5);
    const fillPct = skuItem ? Math.round(skuItem.fill_percentage * 100) : (status === 'empty' ? 0 : status === 'low' ? 25 : 85);

    return {
      shelfId,
      status,
      confidence,
      timestamp,
      skuName,
      skuId,
      brand,
      category,
      facingCount,
      fillPct
    };
  }));

  let lowOrEmptyCount = $derived(cardsData.filter(c => c.status === 'empty' || c.status === 'low').length);
</script>

<div class="bg-white border border-slate-200 rounded-md p-3 sm:p-4 flex flex-col gap-3 shadow-xs">
  <!-- Header with Summary Metrics -->
  <div class="flex items-center justify-between flex-wrap gap-2.5 pb-3 border-b border-slate-100">
    <div>
      <div class="flex items-center gap-2">
        <span class="text-sm font-bold uppercase tracking-wider text-slate-900">SKU Inventory & Shelf Stock</span>
        <span class="px-1.5 py-0.5 text-xs font-mono bg-sky-50 text-sky-700 border border-sky-200 rounded font-semibold">
          EDGE SKU RECOGNITION
        </span>
      </div>
      <p class="text-xs text-slate-500 font-mono mt-0.5">
        Targeted product facing estimation, fill levels & replenishment triage locked to ≥10s cadence.
      </p>
    </div>

    <div class="flex items-center gap-2 flex-wrap text-xs font-mono">
      <span class="px-2 py-1 bg-slate-50 border border-slate-200 text-slate-700 rounded">
        SHELVES: <strong class="text-slate-900">{cardsData.length}</strong>
      </span>
      <span class="px-2 py-1 border rounded {lowOrEmptyCount > 0 ? 'bg-rose-50 border-rose-200 text-rose-700 font-semibold' : 'bg-emerald-50 border-emerald-200 text-emerald-700'}">
        ALERTS: {lowOrEmptyCount}
      </span>
      <span class="px-2 py-1 bg-slate-100 border border-slate-200 text-slate-600 rounded">
        CADENCE: ≥10s
      </span>
    </div>
  </div>

  <!-- SKU Shelf Cards Grid -->
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3 gap-3">
    {#if cardsData.length === 0}
      <div class="col-span-full py-12 text-center text-slate-400 font-mono text-xs">
        NO SHELF STOCK EVENTS RECORDED
      </div>
    {:else}
      {#each cardsData as card (card.shelfId)}
        {@const st = getStatusBadge(card.status)}
        <div class="border rounded-md p-3.5 transition-all flex flex-col justify-between gap-3 shadow-xs bg-white {st.border}">
          <!-- Top Row: SKU Name & Live Status Badge -->
          <div>
            <div class="flex items-start justify-between gap-2 mb-1">
              <div>
                <span class="text-xs font-bold text-slate-900 leading-tight block">
                  {card.skuName}
                </span>
                <div class="flex items-center gap-1.5 mt-1">
                  <span class="px-1.5 py-0.2 text-[10px] font-mono bg-slate-100 text-slate-600 rounded border border-slate-200">
                    {card.skuId}
                  </span>
                  <span class="text-[11px] font-mono text-slate-400">
                    {card.brand} • {card.category}
                  </span>
                </div>
              </div>
              <span class="px-2 py-0.5 text-xs font-mono uppercase font-semibold border rounded shrink-0 {st.badge}">
                {st.label}
              </span>
            </div>

            <div class="text-[11px] font-mono text-slate-500 mt-1 flex items-center gap-1">
              <span>Location:</span>
              <code class="text-slate-800 bg-slate-100 px-1 py-0.5 rounded font-bold">{card.shelfId}</code>
            </div>
          </div>

          <!-- SKU Telemetry: Facings & Fill Level -->
          <div class="bg-slate-50 border border-slate-200 rounded-md p-2.5 flex flex-col gap-2 font-mono text-xs">
            <div class="flex items-center justify-between">
              <span class="text-slate-500">Visible Facings</span>
              <span class="text-slate-900 font-bold">
                {card.facingCount} {card.facingCount === 1 ? 'unit' : 'units'}
              </span>
            </div>

            <div class="space-y-1">
              <div class="flex items-center justify-between text-[11px]">
                <span class="text-slate-500">Shelf Fill Level</span>
                <span class="font-semibold {card.fillPct < 35 ? 'text-rose-700' : card.fillPct < 60 ? 'text-amber-700' : 'text-emerald-700'}">
                  {card.fillPct}%
                </span>
              </div>
              <div class="w-full bg-slate-200 h-2 rounded-sm overflow-hidden">
                <div class="h-full rounded-sm {st.bar} transition-all duration-300" style="width: {card.fillPct}%;"></div>
              </div>
            </div>

            <div class="flex items-center justify-between text-[11px] pt-1 border-t border-slate-200 text-slate-400">
              <span>Classifier Conf</span>
              <span class="text-slate-700 font-semibold">{Math.round(card.confidence * 100)}%</span>
            </div>
          </div>

          <!-- Replenishment Alert Banner if low or empty -->
          {#if st.alertText}
            <div class="px-2 py-1 rounded text-xs font-mono font-medium flex items-center gap-1.5 {card.status === 'empty' ? 'bg-rose-50 border border-rose-200 text-rose-800' : 'bg-amber-50 border border-amber-200 text-amber-800'}">
              <span class="w-1.5 h-1.5 rounded-full {card.status === 'empty' ? 'bg-rose-600' : 'bg-amber-600'}"></span>
              <span>{st.alertText}</span>
            </div>
          {/if}

          <!-- Footer -->
          <div class="text-[11px] font-mono text-slate-400 pt-1 border-t border-slate-100 flex justify-between">
            <span>Cadence: 10s Edge</span>
            <span>{formatTime(card.timestamp)}</span>
          </div>
        </div>
      {/each}
    {/if}
  </div>
</div>

