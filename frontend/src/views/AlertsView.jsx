import React from 'react';
import { AlertTriangle, AlertCircle, Info, CheckCircle2, ShieldCheck } from 'lucide-react';

export default function AlertsView({
  alerts = [],
  activeFilter = 'open',
  onFilterChange,
}) {
  function formatTimestamp(isoStr) {
    if (!isoStr) return '';
    return new Date(isoStr).toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  }

  const filteredAlerts = alerts.filter((a) => {
    if (activeFilter === 'open') return !a.resolved_at;
    if (activeFilter === 'resolved') return !!a.resolved_at;
    return true;
  });

  return (
    <div className="page-content">
      {/* Title & Filter Bar */}
      <div style={styles.titleBar}>
        <div>
          <h1>Incident & Alert Log</h1>
          <p>Real-time edge notifications for queue spillover, low stock, and area congestion.</p>
        </div>

        {/* Filter Tabs */}
        <div style={styles.filterGroup}>
          <button
            onClick={() => onFilterChange && onFilterChange('open')}
            style={{
              ...styles.filterBtn,
              ...(activeFilter === 'open' ? styles.filterBtnActiveDanger : {}),
            }}
          >
            Open Alerts ({alerts.filter((a) => !a.resolved_at).length})
          </button>
          <button
            onClick={() => onFilterChange && onFilterChange('resolved')}
            style={{
              ...styles.filterBtn,
              ...(activeFilter === 'resolved' ? styles.filterBtnActiveSuccess : {}),
            }}
          >
            Resolved
          </button>
          <button
            onClick={() => onFilterChange && onFilterChange('all')}
            style={{
              ...styles.filterBtn,
              ...(activeFilter === 'all' ? styles.filterBtnActive : {}),
            }}
          >
            All Incidents ({alerts.length})
          </button>
        </div>
      </div>

      {/* Alerts List */}
      <div style={styles.list}>
        {filteredAlerts.length > 0 ? (
          filteredAlerts.map((alert) => {
            const isResolved = !!alert.resolved_at;
            const severity = (alert.severity || 'info').toLowerCase();

            const isCritical = severity === 'critical';
            const isWarning = severity === 'warning';

            return (
              <div
                key={alert.id || alert.timestamp}
                className="surface-card"
                style={{
                  ...styles.alertCard,
                  borderColor: isResolved
                    ? 'var(--border-subtle)'
                    : isCritical
                    ? 'var(--status-danger-border)'
                    : isWarning
                    ? 'var(--status-warning-border)'
                    : 'var(--border-subtle)',
                }}
              >
                <div style={styles.alertHeader}>
                  <div style={styles.alertLeft}>
                    {isCritical ? (
                      <AlertCircle size={18} color="#dc2626" />
                    ) : isWarning ? (
                      <AlertTriangle size={18} color="#d97706" />
                    ) : (
                      <Info size={18} color="#0891b2" />
                    )}
                    <span style={styles.alertType}>{alert.alert_type || 'Notification'}</span>
                    <span
                      className={
                        isCritical
                          ? 'badge badge-danger'
                          : isWarning
                          ? 'badge badge-warning'
                          : 'badge badge-info'
                      }
                    >
                      {severity.toUpperCase()}
                    </span>
                  </div>

                  <div style={styles.alertRight}>
                    <span style={styles.timestamp}>{formatTimestamp(alert.timestamp)}</span>
                    {isResolved && (
                      <span className="badge badge-success">
                        <CheckCircle2 size={12} />
                        Resolved
                      </span>
                    )}
                  </div>
                </div>

                <div style={styles.alertMessage}>{alert.message}</div>

                {alert.details && (
                  <div style={styles.detailsBlock}>
                    {typeof alert.details === 'object' ? (
                      Object.entries(alert.details).map(([k, v]) => (
                        <span key={k} style={styles.detailTag}>
                          {k}: <strong>{String(v)}</strong>
                        </span>
                      ))
                    ) : (
                      <span>{String(alert.details)}</span>
                    )}
                  </div>
                )}
              </div>
            );
          })
        ) : (
          <div className="surface-card" style={styles.emptyCard}>
            <ShieldCheck size={36} color="#059669" />
            <div style={{ marginTop: '0.75rem', fontWeight: 600 }}>No {activeFilter} alerts found</div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-subtle)', marginTop: '0.25rem' }}>
              Edge monitoring algorithms report all store zones operating normally.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

const styles = {
  titleBar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  filterGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.35rem',
    backgroundColor: 'var(--bg-muted)',
    padding: '0.2rem',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border-subtle)',
  },
  filterBtn: {
    padding: '0.35rem 0.75rem',
    borderRadius: 'var(--radius-sm)',
    fontSize: '0.775rem',
    color: 'var(--text-muted)',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  filterBtnActive: {
    backgroundColor: 'var(--bg-surface)',
    color: 'var(--text-main)',
    fontWeight: 600,
    boxShadow: 'var(--shadow-xs)',
  },
  filterBtnActiveDanger: {
    backgroundColor: 'var(--status-danger-bg)',
    color: 'var(--status-danger-text)',
    fontWeight: 600,
  },
  filterBtnActiveSuccess: {
    backgroundColor: 'var(--status-success-bg)',
    color: 'var(--status-success-text)',
    fontWeight: 600,
  },
  list: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.75rem',
  },
  alertCard: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.65rem',
    padding: '1rem 1.25rem',
  },
  alertHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  alertLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
  },
  alertType: {
    fontWeight: 600,
    fontSize: '0.9rem',
    color: 'var(--text-main)',
  },
  alertRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
  },
  timestamp: {
    fontSize: '0.75rem',
    color: 'var(--text-subtle)',
  },
  alertMessage: {
    fontSize: '0.85rem',
    color: 'var(--text-muted)',
    lineHeight: 1.45,
  },
  detailsBlock: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '0.5rem',
    paddingTop: '0.4rem',
  },
  detailTag: {
    fontSize: '0.725rem',
    padding: '0.2rem 0.5rem',
    backgroundColor: 'var(--bg-muted)',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--text-subtle)',
    border: '1px solid var(--border-subtle)',
  },
  emptyCard: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    padding: '3.5rem',
    textAlign: 'center',
  },
};
