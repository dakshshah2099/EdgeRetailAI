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

<div class="chart-container">
  <div class="chart-header">
    <div>
      <h3 class="section-title">Footfall Traffic Analytics</h3>
      <p class="section-desc">Temporal distribution of customer enters, exits, and in-store occupancy.</p>
    </div>

    <div class="group-toggle">
      <button 
        type="button"
        class="toggle-btn" 
        class:active={groupBy === 'none'} 
        on:click={() => onGroupByChange('none')}
      >
        Summary
      </button>
      <button 
        type="button"
        class="toggle-btn" 
        class:active={groupBy === 'hour'} 
        on:click={() => onGroupByChange('hour')}
      >
        Hourly
      </button>
      <button 
        type="button"
        class="toggle-btn" 
        class:active={groupBy === 'day'} 
        on:click={() => onGroupByChange('day')}
      >
        Daily
      </button>
    </div>
  </div>

  {#if !footfallData}
    <div class="placeholder">Loading footfall statistics...</div>
  {:else if footfallData.buckets && footfallData.buckets.length > 0}
    {@const maxVal = getMaxBucketCount(footfallData.buckets)}
    <div class="chart-body">
      <div class="bars-container">
        {#each footfallData.buckets as bucket}
          <div class="bar-group">
            <div class="bars-column">
              <div 
                class="bar enter-bar" 
                style="height: {Math.max(4, (bucket.enters / maxVal) * 160)}px;"
                title="Enters: {bucket.enters}"
              ></div>
              <div 
                class="bar exit-bar" 
                style="height: {Math.max(4, (bucket.exits / maxVal) * 160)}px;"
                title="Exits: {bucket.exits}"
              ></div>
            </div>
            <span class="bar-label">{formatBucketTime(bucket.bucket_start)}</span>
          </div>
        {/each}
      </div>

      <div class="chart-legend">
        <div class="legend-item">
          <span class="legend-dot enter-dot"></span>
          <span>Enters ({footfallData.total_enters})</span>
        </div>
        <div class="legend-item">
          <span class="legend-dot exit-dot"></span>
          <span>Exits ({footfallData.total_exits})</span>
        </div>
        <div class="legend-item net-info">
          <span>Net Occupancy: <strong>{footfallData.net_occupancy}</strong></span>
        </div>
      </div>
    </div>
  {:else}
    <div class="summary-card">
      <div class="summary-metrics">
        <div class="sum-item">
          <span class="sum-val text-green">{footfallData.total_enters}</span>
          <span class="sum-lbl">Total Enters</span>
        </div>
        <div class="sum-item">
          <span class="sum-val text-red">{footfallData.total_exits}</span>
          <span class="sum-lbl">Total Exits</span>
        </div>
        <div class="sum-item">
          <span class="sum-val text-blue">{footfallData.net_occupancy}</span>
          <span class="sum-lbl">Current In-Store Occupancy</span>
        </div>
      </div>
      <p class="sum-note">Select "Hourly" or "Daily" grouping to visualize temporal traffic charts.</p>
    </div>
  {/if}
</div>

<style>
  .chart-container {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    box-shadow: var(--shadow-sm);
  }

  .chart-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.75rem;
  }

  .section-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .section-desc {
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .group-toggle {
    display: flex;
    background: #f1f5f9;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    padding: 0.2rem;
  }

  .toggle-btn {
    padding: 0.3rem 0.75rem;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-secondary);
    border-radius: 4px;
    transition: all 0.15s ease;
  }

  .toggle-btn.active {
    background: #ffffff;
    color: var(--accent-blue);
    box-shadow: var(--shadow-sm);
  }

  .chart-body {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .bars-container {
    display: flex;
    align-items: flex-end;
    gap: 1rem;
    height: 190px;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border-color);
    overflow-x: auto;
  }

  .bar-group {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
    flex: 1;
    min-width: 48px;
  }

  .bars-column {
    display: flex;
    align-items: flex-end;
    gap: 4px;
    height: 160px;
  }

  .bar {
    width: 14px;
    border-radius: 3px 3px 0 0;
  }

  .enter-bar {
    background: var(--accent-green);
  }

  .exit-bar {
    background: var(--accent-red);
  }

  .bar-label {
    font-size: 0.72rem;
    font-family: var(--font-mono);
    color: var(--text-muted);
    white-space: nowrap;
  }

  .chart-legend {
    display: flex;
    align-items: center;
    gap: 1.5rem;
    font-size: 0.8rem;
    color: var(--text-secondary);
    padding-top: 0.25rem;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .legend-dot {
    width: 10px;
    height: 10px;
    border-radius: 2px;
  }

  .enter-dot {
    background: var(--accent-green);
  }

  .exit-dot {
    background: var(--accent-red);
  }

  .net-info {
    margin-left: auto;
    font-family: var(--font-mono);
  }

  .net-info strong {
    color: var(--accent-blue);
  }

  .summary-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
    padding: 2.5rem 1rem;
    background: #f8fafc;
    border-radius: var(--radius-md);
    border: 1px solid var(--border-color);
  }

  .summary-metrics {
    display: flex;
    gap: 3.5rem;
    flex-wrap: wrap;
    justify-content: center;
  }

  .sum-item {
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .sum-val {
    font-size: 2.2rem;
    font-weight: 700;
    font-family: var(--font-mono);
  }

  .sum-lbl {
    font-size: 0.75rem;
    color: var(--text-muted);
    font-weight: 500;
  }

  .text-green { color: var(--accent-green); }
  .text-red { color: var(--accent-red); }
  .text-blue { color: var(--accent-blue); }

  .sum-note {
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .placeholder {
    color: var(--text-muted);
    font-size: 0.85rem;
    padding: 2rem;
    text-align: center;
  }
</style>
