<script>
  export let stockEvents = [];

  function formatTime(isoStr) {
    if (!isoStr) return '';
    return new Date(isoStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  function getStatusStyle(status) {
    switch (status) {
      case 'empty': return { label: 'OUT OF STOCK', class: 'status-empty' };
      case 'low': return { label: 'LOW STOCK', class: 'status-low' };
      default: return { label: 'IN STOCK', class: 'status-ok' };
    }
  }
</script>

<div class="stock-container">
  <div class="stock-header">
    <div>
      <h3 class="section-title">Shelf Inventory Health</h3>
      <p class="section-desc">On-device edge ROI vacancy detection across product shelves.</p>
    </div>
    <span class="shelves-count">Monitored Shelves: {stockEvents.length}</span>
  </div>

  <div class="stock-grid">
    {#if stockEvents.length === 0}
      <div class="empty-state">No shelf stock events recorded.</div>
    {:else}
      {#each stockEvents as shelf (shelf.shelf_id)}
        {@const st = getStatusStyle(shelf.status)}
        <div class="shelf-card {st.class}">
          <div class="shelf-top">
            <div class="shelf-name">
              <span class="shelf-indicator"></span>
              <strong>{shelf.shelf_id}</strong>
            </div>
            <span class="status-pill">{st.label}</span>
          </div>

          <div class="shelf-confidence">
            <div class="conf-labels">
              <span>Classifier Confidence</span>
              <strong>{Math.round(shelf.confidence * 100)}%</strong>
            </div>
            <div class="conf-bar">
              <div class="conf-fill" style="width: {Math.round(shelf.confidence * 100)}%;"></div>
            </div>
          </div>

          <div class="shelf-footer">
            <span>Last checked: {formatTime(shelf.timestamp)}</span>
          </div>
        </div>
      {/each}
    {/if}
  </div>
</div>

<style>
  .stock-container {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    box-shadow: var(--shadow-sm);
  }

  .stock-header {
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

  .shelves-count {
    font-size: 0.72rem;
    font-family: var(--font-mono);
    color: var(--text-secondary);
    background: #f1f5f9;
    border: 1px solid var(--border-color);
    padding: 0.2rem 0.55rem;
    border-radius: var(--radius-sm);
  }

  .stock-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 1rem;
  }

  .empty-state {
    grid-column: 1 / -1;
    padding: 3rem;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.88rem;
  }

  .shelf-card {
    background: #ffffff;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 1.15rem;
    display: flex;
    flex-direction: column;
    gap: 0.85rem;
    transition: all 0.15s ease;
  }

  .shelf-card:hover {
    box-shadow: var(--shadow-md);
  }

  .shelf-card.status-empty {
    border-color: #fca5a5;
    background: #fff8f8;
  }

  .shelf-card.status-low {
    border-color: #fde047;
    background: #fffdf5;
  }

  .shelf-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .shelf-name {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.92rem;
    color: var(--text-primary);
  }

  .shelf-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }

  .status-ok .shelf-indicator { background: var(--accent-green); }
  .status-low .shelf-indicator { background: var(--accent-amber); }
  .status-empty .shelf-indicator { background: var(--accent-red); }

  .status-pill {
    font-size: 0.65rem;
    font-weight: 700;
    font-family: var(--font-mono);
    padding: 0.15rem 0.45rem;
    border-radius: 4px;
  }

  .status-empty .status-pill {
    background: var(--accent-red-light);
    color: var(--accent-red);
    border: 1px solid #fca5a5;
  }

  .status-low .status-pill {
    background: var(--accent-amber-light);
    color: var(--accent-amber);
    border: 1px solid #fde047;
  }

  .status-ok .status-pill {
    background: var(--accent-green-light);
    color: var(--accent-green);
    border: 1px solid #a7f3d0;
  }

  .shelf-confidence {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }

  .conf-labels {
    display: flex;
    justify-content: space-between;
    font-size: 0.72rem;
    color: var(--text-muted);
  }

  .conf-labels strong {
    font-family: var(--font-mono);
    color: var(--text-secondary);
  }

  .conf-bar {
    height: 6px;
    background: #f1f5f9;
    border-radius: 3px;
    overflow: hidden;
    border: 1px solid #e2e8f0;
  }

  .conf-fill {
    height: 100%;
    border-radius: 3px;
    background: var(--accent-blue);
  }

  .status-empty .conf-fill { background: var(--accent-red); }
  .status-low .conf-fill { background: var(--accent-amber); }
  .status-ok .conf-fill { background: var(--accent-green); }

  .shelf-footer {
    font-size: 0.72rem;
    color: var(--text-muted);
    font-family: var(--font-mono);
    border-top: 1px solid #f1f5f9;
    padding-top: 0.5rem;
  }
</style>
