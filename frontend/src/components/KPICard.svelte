<script>
  export let title = '';
  export let value = '0';
  export let subtitle = '';
  export let icon = 'chart';
  export let tag = '';
  export let status = 'normal'; // 'normal' | 'success' | 'warning' | 'danger'

  const statusBorderMap = {
    normal: 'border-slate-200 hover:border-slate-300 bg-white',
    success: 'border-emerald-200 hover:border-emerald-300 bg-emerald-50/40',
    warning: 'border-amber-200 hover:border-amber-300 bg-amber-50/40',
    danger: 'border-rose-200 hover:border-rose-300 bg-rose-50/40'
  };

  const statusPillMap = {
    normal: 'bg-slate-100 text-slate-700 border-slate-200',
    success: 'bg-emerald-100 text-emerald-800 border-emerald-200',
    warning: 'bg-amber-100 text-amber-800 border-amber-200',
    danger: 'bg-rose-100 text-rose-800 border-rose-200'
  };

  const statusValueColor = {
    normal: 'text-slate-900',
    success: 'text-emerald-700',
    warning: 'text-amber-700',
    danger: 'text-rose-700'
  };
</script>

<div class="relative flex flex-col justify-between p-3.5 border rounded-md shadow-xs transition-all duration-150 {statusBorderMap[status] || statusBorderMap.normal}">
  <!-- Card Header / Meta -->
  <div class="flex items-center justify-between gap-2 mb-1.5">
    <div class="flex items-center gap-2">
      <div class="w-6 h-6 flex items-center justify-center rounded bg-slate-100 text-slate-600">
        {#if icon === 'occupancy'}
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
          </svg>
        {:else if icon === 'footfall'}
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
            <polyline points="17 6 23 6 23 12"/>
          </svg>
        {:else if icon === 'queue'}
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="1" y="4" width="22" height="16" rx="2" ry="2"/>
            <line x1="1" y1="10" x2="23" y2="10"/>
          </svg>
        {:else if icon === 'stock'}
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 16v26a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v26a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
            <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
            <line x1="12" y1="22.08" x2="12" y2="12"/>
          </svg>
        {:else}
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
            <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
          </svg>
        {/if}
      </div>
      <span class="text-xs font-semibold uppercase tracking-wider text-slate-500">{title}</span>
    </div>
    {#if tag}
      <span class="px-1.5 py-0.5 text-xs font-mono uppercase tracking-wider border rounded {statusPillMap[status] || statusPillMap.normal}">
        {tag}
      </span>
    {/if}
  </div>

  <!-- Readout Value -->
  <div class="my-0.5">
    <span class="text-2xl font-mono font-semibold tracking-tight {statusValueColor[status] || statusValueColor.normal}">
      {value}
    </span>
  </div>

  <!-- Subtitle / Context -->
  {#if subtitle}
    <div class="mt-1 pt-1.5 border-t border-slate-100 text-xs font-mono text-slate-500 flex items-center justify-between">
      <span>{subtitle}</span>
    </div>
  {/if}
</div>
