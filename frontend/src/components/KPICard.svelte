<script>
  export let title = '';
  export let value = '0';
  export let subtitle = '';
  export let icon = 'chart'; // 'occupancy' | 'footfall' | 'queue' | 'stock' | 'alerts'
  export let tag = '';
  export let status = 'normal'; // 'normal' | 'success' | 'warning' | 'danger'
</script>

<div class="kpi-card status-{status}">
  <div class="card-top">
    <div class="card-icon">
      {#if icon === 'occupancy'}
        <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
          <circle cx="9" cy="7" r="4"/>
          <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
          <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
        </svg>
      {:else if icon === 'footfall'}
        <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none">
          <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
          <polyline points="17 6 23 6 23 12"/>
        </svg>
      {:else if icon === 'queue'}
        <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none">
          <rect x="1" y="4" width="22" height="16" rx="2" ry="2"/>
          <line x1="1" y1="10" x2="23" y2="10"/>
        </svg>
      {:else if icon === 'stock'}
        <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none">
          <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
          <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
          <line x1="12" y1="22.08" x2="12" y2="12"/>
        </svg>
      {:else}
        <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
          <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
        </svg>
      {/if}
    </div>
    {#if tag}
      <span class="card-tag">{tag}</span>
    {/if}
  </div>

  <div class="card-body">
    <span class="card-title">{title}</span>
    <span class="card-value">{value}</span>
  </div>

  {#if subtitle}
    <div class="card-footer">
      <span>{subtitle}</span>
    </div>
  {/if}
</div>

<style>
  .kpi-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    padding: 1.15rem;
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
    box-shadow: var(--shadow-sm);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
  }

  .kpi-card:hover {
    transform: translateY(-1px);
    box-shadow: var(--shadow-md);
  }

  .card-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .card-icon {
    width: 34px;
    height: 34px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-sm);
    background: #f1f5f9;
    color: var(--text-secondary);
  }

  .card-tag {
    font-size: 0.7rem;
    font-weight: 600;
    padding: 0.15rem 0.5rem;
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
  }

  .card-body {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }

  .card-title {
    font-size: 0.8rem;
    color: var(--text-muted);
    font-weight: 500;
  }

  .card-value {
    font-size: 1.65rem;
    font-weight: 700;
    color: var(--text-primary);
    font-family: var(--font-mono);
    letter-spacing: -0.03em;
  }

  .card-footer {
    font-size: 0.75rem;
    color: var(--text-muted);
    border-top: 1px solid #f1f5f9;
    padding-top: 0.5rem;
  }

  /* Status variants */
  .status-normal .card-icon { background: var(--accent-blue-light); color: var(--accent-blue); }
  .status-normal .card-tag { background: var(--accent-blue-light); color: var(--accent-blue); border: 1px solid #bfdbfe; }

  .status-success .card-icon { background: var(--accent-green-light); color: var(--accent-green); }
  .status-success .card-tag { background: var(--accent-green-light); color: var(--accent-green); border: 1px solid #a7f3d0; }

  .status-warning .card-icon { background: var(--accent-amber-light); color: var(--accent-amber); }
  .status-warning .card-tag { background: var(--accent-amber-light); color: var(--accent-amber); border: 1px solid #fde68a; }

  .status-danger .card-icon { background: var(--accent-red-light); color: var(--accent-red); }
  .status-danger .card-tag { background: var(--accent-red-light); color: var(--accent-red); border: 1px solid #fecaca; }
</style>
