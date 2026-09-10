<script>
  export let isConnected = true;
  export let lastUpdated = new Date();
  export let isRefreshing = false;
  export let autoRefresh = true;
  export let refreshInterval = 3;
  export let selectedTimeRange = 'all';
  export let selectedZone = '';
  export let onRefresh = () => {};
  export let onToggleMobileMenu = () => {};

  function formatTime(date) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
</script>

<header class="bg-white border-b border-slate-200 text-slate-900 px-3 sm:px-4 py-2 sm:py-2.5 flex items-center justify-between gap-2 flex-wrap select-none sticky top-0 z-30 shadow-xs shrink-0">
  <!-- Left: Mobile Menu Toggle & Operational Context -->
  <div class="flex items-center gap-2 sm:gap-3">
    <button
      type="button"
      class="p-1.5 rounded-md text-slate-600 hover:text-slate-900 hover:bg-slate-100 border border-slate-200 md:hidden flex items-center justify-center cursor-pointer shadow-xs"
      on:click={onToggleMobileMenu}
      aria-label="Open navigation menu"
      title="Open navigation menu"
    >
      <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="3" y1="12" x2="21" y2="12"/>
        <line x1="3" y1="6" x2="21" y2="6"/>
        <line x1="3" y1="18" x2="21" y2="18"/>
      </svg>
    </button>
    <div>
      <span class="text-xs font-mono font-semibold uppercase text-slate-500 tracking-wider">System Operations</span>
    </div>
  </div>

  <!-- Right: Operational Controls & Status -->
  <div class="flex items-center gap-1.5 sm:gap-2.5 flex-wrap justify-end">
    <!-- Range Filter -->
    <div class="flex items-center bg-slate-50 border border-slate-200 rounded-md px-2 py-1 text-xs">
      <span class="text-slate-500 font-mono mr-1.5 uppercase text-xs">Range</span>
      <select 
        class="bg-transparent text-slate-800 font-mono text-xs focus:outline-none cursor-pointer"
        bind:value={selectedTimeRange} 
        on:change={onRefresh}
      >
        <option value="all">ALL TIME</option>
        <option value="1h">1 HOUR</option>
        <option value="6h">6 HOURS</option>
        <option value="24h">24 HOURS</option>
      </select>
    </div>

    <!-- Zone Filter -->
    <div class="flex items-center bg-slate-50 border border-slate-200 rounded-md px-2 py-1 text-xs">
      <span class="text-slate-500 font-mono mr-1.5 uppercase text-xs">Zone</span>
      <input 
        type="text" 
        placeholder="ALL ZONES" 
        class="bg-transparent text-slate-800 font-mono text-xs focus:outline-none w-20 sm:w-24 placeholder-slate-400"
        bind:value={selectedZone} 
        on:input={onRefresh}
      />
    </div>

    <!-- Edge Health Status Badge -->
    <div class="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-md px-2.5 py-1 text-xs font-mono">
      <span class="relative flex h-2 w-2">
        {#if isConnected}
          <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
          <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-600"></span>
        {:else}
          <span class="relative inline-flex rounded-full h-2 w-2 bg-rose-600"></span>
        {/if}
      </span>
      <span class={isConnected ? 'text-emerald-700 font-semibold' : 'text-rose-700 font-semibold'}>
        {isConnected ? 'NODE ONLINE' : 'NODE OFFLINE'}
      </span>
      <span class="text-slate-300">|</span>
      <span class="text-slate-500 text-xs">{formatTime(lastUpdated)}</span>
    </div>

    <!-- Auto-refresh and Manual Pulse -->
    <div class="flex items-center gap-1 bg-slate-50 border border-slate-200 rounded-md px-2 py-1 text-xs font-mono">
      <label class="flex items-center gap-1.5 cursor-pointer select-none">
        <input type="checkbox" class="accent-sky-600 cursor-pointer" bind:checked={autoRefresh} />
        <span class="text-slate-600 text-xs font-medium">AUTO</span>
      </label>
      <select 
        class="bg-transparent text-slate-700 text-xs focus:outline-none cursor-pointer ml-1"
        bind:value={refreshInterval}
        disabled={!autoRefresh}
      >
        <option value={1}>1s</option>
        <option value={3}>3s</option>
        <option value={5}>5s</option>
        <option value={10}>10s</option>
      </select>

      <button 
        type="button" 
        class="ml-1 p-1 text-slate-500 hover:text-sky-600 transition-colors"
        class:animate-spin={isRefreshing}
        on:click={onRefresh}
        title="Force Refresh Data"
      >
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="23 4 23 10 17 10"/>
          <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
        </svg>
      </button>
    </div>
  </div>
</header>
