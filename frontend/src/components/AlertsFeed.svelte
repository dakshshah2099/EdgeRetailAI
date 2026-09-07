<script>
  export let alerts = [];
  export let activeFilter = 'open';
  export let onFilterChange = (status) => {};

  function formatTimestamp(isoStr) {
    if (!isoStr) return '';
    const date = new Date(isoStr);
    return date.toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }
</script>

<div class="alerts-container">
  <div class="alerts-header">
    <div>
      <h3 class="section-title">System Alerts Log</h3>
      <p class="section-desc">Automated stock depletion and checkout queue congestion notifications.</p>
    </div>

    <div class="filter-tabs">
      <button 
        type="button"
        class="tab-btn" 
        class:active={activeFilter === 'open'} 
        on:click={() => onFilterChange('open')}
      >
        Open
      </button>
      <button 
        type="button"
        class="tab-btn" 
        class:active={activeFilter === 'resolved'} 
        on:click={() => onFilterChange('resolved')}
      >
        Resolved
      </button>
      <button 
        type="button"
        class="tab-btn" 
        class:active={activeFilter === 'all'} 
        on:click={() => onFilterChange('all')}
      >
        All
      </button>
    </div>
  </div>

  <div class="alerts-list">
    {#if alerts.length === 0}
      <div class="empty-state">
        <svg viewBox="0 0 24 24" width="32" height="32" stroke="#059669" stroke-width="2" fill="none">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
          <polyline points="22 4 12 14.01 9 11.01"/>
        </svg>
        <p>No {activeFilter} alerts found.</p>
      </div>
    {:else}
      {#each alerts as alert (alert.alert_id)}
        <div class="alert-card severity-{alert.severity}" class:resolved={!!alert.resolved_at}>
          <div class="alert-content">
            <div class="alert-top">
              <span class="severity-pill pill-{alert.severity}">{alert.severity.toUpperCase()}</span>
              <span class="type-pill">{alert.alert_type}</span>
              {#if alert.zone_id}
                <span class="zone-pill">Zone: {alert.zone_id}</span>
              {/if}
              {#if alert.resolved_at}
                <span class="status-badge resolved-text">✓ Resolved</span>
              {:else}
                <span class="status-badge active-text">● Active</span>
              {/if}
            </div>

            <div class="alert-message">{alert.message}</div>

            <div class="alert-timestamps">
              <span>Created: <strong>{formatTimestamp(alert.created_at)}</strong></span>
              {#if alert.resolved_at}
                <span>• Resolved: <strong>{formatTimestamp(alert.resolved_at)}</strong></span>
              {/if}
            </div>
          </div>
        </div>
      {/each}
    {/if}
  </div>
</div>

<style>
  .alerts-container {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    box-shadow: var(--shadow-sm);
  }

  .alerts-header {
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

  .filter-tabs {
    display: flex;
    background: #f1f5f9;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    padding: 0.2rem;
  }

  .tab-btn {
    padding: 0.3rem 0.8rem;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-secondary);
    border-radius: 4px;
    transition: all 0.15s ease;
  }

  .tab-btn.active {
    background: #ffffff;
    color: var(--accent-blue);
    box-shadow: var(--shadow-sm);
  }

  .alerts-list {
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
    max-height: 420px;
    overflow-y: auto;
    padding-right: 0.25rem;
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3rem 1rem;
    color: var(--text-muted);
    gap: 0.6rem;
    font-size: 0.88rem;
  }

  .alert-card {
    display: flex;
    padding: 0.9rem 1.1rem;
    background: #ffffff;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    transition: all 0.15s ease;
  }

  .alert-card:hover {
    background: #f8fafc;
    border-color: #cbd5e1;
  }

  .alert-card.severity-critical {
    background: #fff8f8;
    border-color: #fecaca;
  }

  .alert-card.severity-warning {
    background: #fffdf5;
    border-color: #fef08a;
  }

  .alert-card.severity-info {
    background: #f8faff;
    border-color: #bfdbfe;
  }

  .alert-card.resolved {
    background: #ffffff;
    border-color: var(--border-color);
    opacity: 0.75;
  }

  .alert-content {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    flex: 1;
  }

  .alert-top {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .severity-pill {
    font-size: 0.65rem;
    font-weight: 700;
    font-family: var(--font-mono);
    padding: 0.12rem 0.45rem;
    border-radius: 4px;
  }

  .pill-critical { background: var(--accent-red-light); color: var(--accent-red); border: 1px solid #fca5a5; }
  .pill-warning { background: var(--accent-amber-light); color: var(--accent-amber); border: 1px solid #fde047; }
  .pill-info { background: var(--accent-blue-light); color: var(--accent-blue); border: 1px solid #bfdbfe; }

  .type-pill, .zone-pill {
    font-size: 0.7rem;
    color: var(--text-secondary);
    background: #f1f5f9;
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
  }

  .active-text {
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--accent-amber);
    margin-left: auto;
  }

  .resolved-text {
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--accent-green);
    margin-left: auto;
  }

  .alert-message {
    font-size: 0.88rem;
    color: var(--text-primary);
    font-weight: 500;
  }

  .alert-timestamps {
    font-size: 0.72rem;
    color: var(--text-muted);
    font-family: var(--font-mono);
    display: flex;
    gap: 0.5rem;
  }

  .alert-timestamps strong {
    color: var(--text-secondary);
  }
</style>
