import React from 'react';
import { RefreshCw, CheckCircle2, AlertTriangle, Video } from 'lucide-react';

export default function Header({
  isConnected = false,
  isRefreshing = false,
  lastUpdated = new Date(),
  openAlertsCount = 0,
  refreshIntervalSec = 3,
  selectedTimeRange = 'all',
  selectedZone = '',
  onTimeRangeChange,
  onZoneChange,
  onRefreshIntervalChange,
  onRefresh,
}) {
  const formattedTime = lastUpdated
    ? new Date(lastUpdated).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '--:--:--';

  const hasIssues = openAlertsCount > 0;

  return (
    <header style={styles.header}>
      {/* Left: Store Status Summary */}
      <div style={styles.leftSection}>
        <div style={styles.storeTag}>
          <span style={styles.storeName}>Main Store</span>
          <span style={styles.storeLocation}>Ground Floor</span>
        </div>

        {/* Store Health Status Pill */}
        <div
          style={{
            ...styles.statusPill,
            backgroundColor: !isConnected
              ? 'var(--status-danger-bg)'
              : hasIssues
              ? 'var(--status-warning-bg)'
              : 'var(--status-success-bg)',
            borderColor: !isConnected
              ? 'var(--status-danger-border)'
              : hasIssues
              ? 'var(--status-warning-border)'
              : 'var(--status-success-border)',
            color: !isConnected
              ? 'var(--status-danger-text)'
              : hasIssues
              ? 'var(--status-warning-text)'
              : 'var(--status-success-text)',
          }}
        >
          {!isConnected ? (
            <>
              <AlertTriangle size={14} />
              <span>Camera Node Offline</span>
            </>
          ) : hasIssues ? (
            <>
              <AlertTriangle size={14} />
              <span>{openAlertsCount} Alerts Needing Attention</span>
            </>
          ) : (
            <>
              <CheckCircle2 size={14} />
              <span>Store Operating Normally</span>
            </>
          )}
        </div>
      </div>

      {/* Right: Store Manager Filters & Refresh */}
      <div style={styles.rightSection}>
        {/* Time Window */}
        <select
          value={selectedTimeRange}
          onChange={(e) => onTimeRangeChange && onTimeRangeChange(e.target.value)}
          style={styles.select}
          aria-label="Select time range"
        >
          <option value="all">Today (All Data)</option>
          <option value="1h">Last 1 Hour</option>
          <option value="6h">Last 6 Hours</option>
          <option value="24h">Last 24 Hours</option>
        </select>

        {/* Zone Selector */}
        <select
          value={selectedZone}
          onChange={(e) => onZoneChange && onZoneChange(e.target.value)}
          style={styles.select}
          aria-label="Filter by store area"
        >
          <option value="">All Store Areas</option>
          <option value="zone_entrance">Entrance</option>
          <option value="zone_checkout">Checkout Counters</option>
          <option value="zone_aisle_1">Grocery Aisle</option>
          <option value="zone_aisle_2">Snacks Aisle</option>
        </select>

        {/* Auto Refresh Frequency */}
        <select
          value={refreshIntervalSec}
          onChange={(e) => onRefreshIntervalChange && onRefreshIntervalChange(Number(e.target.value))}
          style={styles.select}
          aria-label="Auto-update frequency"
        >
          <option value={2}>Live (2s)</option>
          <option value={3}>Normal (3s)</option>
          <option value={5}>Relaxed (5s)</option>
          <option value={10}>Slow (10s)</option>
        </select>

        {/* Refresh Sync Button */}
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          style={styles.refreshBtn}
          title={`Last synced at ${formattedTime}`}
          aria-label="Sync store data now"
        >
          <RefreshCw
            size={13}
            style={{
              animation: isRefreshing ? 'spin 1s linear infinite' : 'none',
            }}
          />
          <span>{isRefreshing ? 'Syncing...' : 'Sync'}</span>
        </button>
      </div>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </header>
  );
}

const styles = {
  header: {
    height: 'var(--header-height)',
    backgroundColor: 'var(--bg-surface)',
    borderBottom: '1px solid var(--border-subtle)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 1.5rem',
    flexShrink: 0,
    gap: '1rem',
  },
  leftSection: {
    display: 'flex',
    alignItems: 'center',
    gap: '1rem',
  },
  storeTag: {
    display: 'flex',
    flexDirection: 'column',
    lineHeight: 1.2,
  },
  storeName: {
    fontSize: '0.875rem',
    fontWeight: 700,
    color: 'var(--text-main)',
  },
  storeLocation: {
    fontSize: '0.7rem',
    color: 'var(--text-subtle)',
  },
  statusPill: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.4rem',
    padding: '0.25rem 0.65rem',
    borderRadius: '9999px',
    border: '1px solid transparent',
    fontSize: '0.775rem',
    fontWeight: 600,
  },
  rightSection: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
  },
  select: {
    padding: '0.35rem 0.6rem',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border-subtle)',
    backgroundColor: 'var(--bg-surface)',
    color: 'var(--text-main)',
    fontSize: '0.775rem',
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'border-color 0.15s ease',
  },
  refreshBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.35rem',
    padding: '0.35rem 0.7rem',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border-subtle)',
    backgroundColor: 'var(--bg-surface)',
    color: 'var(--text-main)',
    fontSize: '0.775rem',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'background-color 0.15s ease, border-color 0.15s ease',
  },
};
