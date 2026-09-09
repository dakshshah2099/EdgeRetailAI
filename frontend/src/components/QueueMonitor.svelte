<script>
  export let queueEvents = [];
  export let congestionThreshold = 4;

  function formatTime(isoStr) {
    if (!isoStr) return '';
    return new Date(isoStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
</script>

<div class="queue-container">
  <div class="queue-header">
    <div>
      <h3 class="section-title">Checkout Queue Intelligence</h3>
      <p class="section-desc">Real-time checkout counter monitoring and customer wait-time forecasting.</p>
    </div>
    <span class="threshold-badge">Congestion Threshold: ≥ {congestionThreshold} persons</span>
  </div>

  <div class="counters-grid">
    {#if queueEvents.length === 0}
      <div class="empty-state">No checkout counter telemetry recorded.</div>
    {:else}
      {#each queueEvents as item (item.counter_id)}
        {@const isCongested = item.queue_length >= congestionThreshold}
        {@const isPredCongested = !isCongested && item.predicted_queue_length != null && item.predicted_queue_length >= congestionThreshold}
        <div class="counter-card" class:congested={isCongested} class:warning-pred={isPredCongested}>
          <div class="counter-top">
            <span class="counter-id">Counter: <strong>{item.counter_id}</strong></span>
            {#if isCongested}
              <span class="badge badge-danger">Congested</span>
            {:else if isPredCongested}
              <span class="badge badge-warning">Surge Predicted</span>
            {:else}
              <span class="badge badge-normal">Optimal</span>
            {/if}
          </div>

          <div class="counter-stats">
            <div class="stat-block">
              <span class="stat-label">Queue Length</span>
              <span class="stat-value">{item.queue_length} <small>persons</small></span>
            </div>

            <div class="stat-block">
              <span class="stat-label">Est. Wait Time</span>
              <span class="stat-value">
                {item.avg_wait_est_sec != null ? `${Math.round(item.avg_wait_est_sec)}s` : 'N/A'}
              </span>
            </div>
          </div>

          {#if item.predicted_queue_length != null}
            <div class="forecast-banner">
              <span class="forecast-label">Forecast (3m):</span>
              <span class="forecast-value">~{item.predicted_queue_length} persons ({Math.round(item.predicted_wait_sec ?? 0)}s)</span>
            </div>
          {/if}

          <!-- Queue progress visualization dots -->
          <div class="queue-visual">
            {#each Array(Math.min(10, Math.max(item.queue_length, 1))) as _, i}
              <span 
                class="person-dot" 
                class:active={i < item.queue_length}
                class:alert-person={isCongested && i >= congestionThreshold - 1}
              ></span>
            {/each}
          </div>

          <div class="counter-footer">
            <span>Last reading: {formatTime(item.timestamp)}</span>
          </div>
        </div>
      {/each}
    {/if}
  </div>
</div>

<style>
  .queue-container {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    box-shadow: var(--shadow-sm);
  }

  .queue-header {
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

  .threshold-badge {
    font-size: 0.72rem;
    font-family: var(--font-mono);
    color: var(--accent-amber);
    background: var(--accent-amber-light);
    border: 1px solid #fde68a;
    padding: 0.2rem 0.55rem;
    border-radius: var(--radius-sm);
    font-weight: 500;
  }

  .counters-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1rem;
  }

  .empty-state {
    grid-column: 1 / -1;
    padding: 3rem;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.88rem;
  }

  .counter-card {
    background: #ffffff;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 1.15rem;
    display: flex;
    flex-direction: column;
    gap: 0.85rem;
    transition: all 0.15s ease;
  }

  .counter-card:hover {
    box-shadow: var(--shadow-md);
  }

  .counter-card.congested {
    border-color: #fca5a5;
    background: #fff8f8;
  }

  .counter-card.warning-pred {
    border-color: #fde047;
    background: #fefce8;
  }

  .counter-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .counter-id {
    font-size: 0.9rem;
    color: var(--text-secondary);
  }

  .counter-id strong {
    color: var(--text-primary);
  }

  .badge {
    font-size: 0.7rem;
    font-weight: 600;
    padding: 0.15rem 0.45rem;
    border-radius: 4px;
    font-family: var(--font-mono);
  }

  .badge-normal {
    background: var(--accent-green-light);
    color: var(--accent-green);
    border: 1px solid #a7f3d0;
  }

  .badge-danger {
    background: var(--accent-red-light);
    color: var(--accent-red);
    border: 1px solid #fca5a5;
  }

  .badge-warning {
    background: #fef9c3;
    color: #854d0e;
    border: 1px solid #fde047;
  }

  .forecast-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #f1f5f9;
    padding: 0.35rem 0.6rem;
    border-radius: var(--radius-sm);
    font-size: 0.73rem;
  }

  .forecast-label {
    color: var(--text-muted);
    font-weight: 500;
  }

  .forecast-value {
    color: #0f766e;
    font-weight: 600;
    font-family: var(--font-mono);
  }

  .counter-stats {
    display: flex;
    justify-content: space-between;
    background: #f8fafc;
    padding: 0.6rem 0.85rem;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-color);
  }

  .stat-block {
    display: flex;
    flex-direction: column;
  }

  .stat-label {
    font-size: 0.7rem;
    color: var(--text-muted);
  }

  .stat-value {
    font-size: 1.25rem;
    font-weight: 700;
    font-family: var(--font-mono);
    color: var(--text-primary);
  }

  .stat-value small {
    font-size: 0.75rem;
    font-weight: 400;
    color: var(--text-muted);
  }

  .queue-visual {
    display: flex;
    gap: 6px;
    align-items: center;
    padding: 0.25rem 0;
  }

  .person-dot {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: #e2e8f0;
    border: 1px solid #cbd5e1;
  }

  .person-dot.active {
    background: var(--accent-blue);
    border-color: #1d4ed8;
  }

  .person-dot.alert-person {
    background: var(--accent-red);
    border-color: #b91c1c;
  }

  .counter-footer {
    font-size: 0.72rem;
    color: var(--text-muted);
    font-family: var(--font-mono);
    border-top: 1px solid #f1f5f9;
    padding-top: 0.5rem;
  }
</style>
