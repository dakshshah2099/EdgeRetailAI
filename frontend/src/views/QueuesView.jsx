import React from 'react';
import { Users, Clock, AlertTriangle, CheckCircle, ArrowRight } from 'lucide-react';

export default function QueuesView({ queueEvents = [], congestionThreshold = 4 }) {
  const congestedCounters = queueEvents.filter(
    (item) => item.queue_length >= congestionThreshold
  );

  return (
    <div className="page-content">
      {/* Title */}
      <div style={styles.titleBar}>
        <div>
          <h1>Checkout Queue Intelligence</h1>
          <p>Real-time line length tracking, wait time forecasting, and cashier allocation.</p>
        </div>

        <div style={styles.thresholdBadge}>
          <span>Congestion Threshold:</span>
          <strong>≥ {congestionThreshold} persons</strong>
        </div>
      </div>

      {/* Congestion Notice Banner */}
      {congestedCounters.length > 0 && (
        <div style={styles.alertBanner}>
          <div style={styles.alertBannerLeft}>
            <AlertTriangle size={18} color="#dc2626" />
            <div>
              <div style={styles.alertTitle}>Checkout Congestion Detected</div>
              <div style={styles.alertDesc}>
                {congestedCounters.map((c) => c.counter_id).join(', ')} exceeded wait threshold.
                Recommended action: Open 1 additional checkout counter.
              </div>
            </div>
          </div>
          <span className="badge badge-danger">Action Required</span>
        </div>
      )}

      {/* Checkout Counter Cards Grid */}
      <div style={styles.grid}>
        {queueEvents.length > 0 ? (
          queueEvents.map((item) => {
            const isCongested = item.queue_length >= congestionThreshold;
            return (
              <div
                key={item.counter_id}
                className="surface-card"
                style={{
                  ...styles.counterCard,
                  borderColor: isCongested ? 'var(--status-danger-border)' : 'var(--border-subtle)',
                }}
              >
                <div style={styles.cardHeader}>
                  <div style={styles.counterTitle}>
                    <Users size={16} color={isCongested ? '#dc2626' : '#2563eb'} />
                    <span>Register: <strong>{item.counter_id}</strong></span>
                  </div>
                  <span
                    className={
                      isCongested ? 'badge badge-danger' : 'badge badge-success'
                    }
                  >
                    {isCongested ? 'Congested' : 'Optimal'}
                  </span>
                </div>

                <div style={styles.statsRow}>
                  <div style={styles.statBlock}>
                    <span style={styles.statLabel}>Current Line</span>
                    <span style={styles.statVal}>
                      {item.queue_length} <small style={styles.statUnit}>persons</small>
                    </span>
                  </div>
                  <div style={styles.statBlock}>
                    <span style={styles.statLabel}>Est. Wait Time</span>
                    <span style={styles.statVal}>
                      {item.avg_wait_est_sec != null ? `${Math.round(item.avg_wait_est_sec)}s` : '0s'}
                    </span>
                  </div>
                </div>

                {/* Queue Person Dots Visualization */}
                <div style={styles.queueViz}>
                  <div style={styles.vizLabel}>Line Visualization:</div>
                  <div style={styles.dotsRow}>
                    {Array.from({ length: Math.min(12, Math.max(item.queue_length, 4)) }).map(
                      (_, idx) => {
                        const isOccupied = idx < item.queue_length;
                        const isSpillover = isOccupied && idx >= congestionThreshold;
                        return (
                          <span
                            key={idx}
                            style={{
                              ...styles.personDot,
                              backgroundColor: isSpillover
                                ? '#ef4444'
                                : isOccupied
                                ? '#2563eb'
                                : '#e2e8f0',
                            }}
                            title={`Position ${idx + 1}`}
                          />
                        );
                      }
                    )}
                  </div>
                </div>
              </div>
            );
          })
        ) : (
          <div className="surface-card" style={styles.emptyCard}>
            <Users size={28} color="#94a3b8" />
            <div style={{ marginTop: '0.5rem', fontWeight: 500 }}>No Queue Events Detected</div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-subtle)' }}>
              Camera edge queue monitor is polling for customer checkout formations...
            </p>
          </div>
        )}
      </div>

      {/* Historical Queue Data Table */}
      <section className="surface-card">
        <div style={{ marginBottom: '1rem' }}>
          <h2>Checkout Registers Telemetry Log</h2>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-subtle)' }}>
            Individual counter event history and wait times
          </p>
        </div>

        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Register Name</th>
                <th>Queue Length</th>
                <th>Est. Wait Time</th>
                <th>Congestion Status</th>
                <th>Recorded At</th>
              </tr>
            </thead>
            <tbody>
              {queueEvents.length > 0 ? (
                queueEvents.map((item) => (
                  <tr key={item.counter_id}>
                    <td style={{ fontWeight: 600 }}>{item.counter_id}</td>
                    <td>{item.queue_length} shoppers</td>
                    <td>{item.avg_wait_est_sec != null ? `${Math.round(item.avg_wait_est_sec)}s` : '0s'}</td>
                    <td>
                      <span
                        className={
                          item.queue_length >= congestionThreshold
                            ? 'badge badge-danger'
                            : 'badge badge-success'
                        }
                      >
                        {item.queue_length >= congestionThreshold ? 'Congested' : 'Clear'}
                      </span>
                    </td>
                    <td style={{ color: 'var(--text-subtle)', fontSize: '0.8rem' }}>
                      {item.timestamp ? new Date(item.timestamp).toLocaleTimeString() : 'Just now'}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-subtle)' }}>
                    No queue log data available.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

const styles = {
  titleBar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  thresholdBadge: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.4rem',
    padding: '0.35rem 0.75rem',
    borderRadius: 'var(--radius-sm)',
    backgroundColor: 'var(--bg-surface)',
    border: '1px solid var(--border-subtle)',
    fontSize: '0.8rem',
    color: 'var(--text-muted)',
  },
  alertBanner: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0.85rem 1.25rem',
    borderRadius: 'var(--radius-md)',
    backgroundColor: 'var(--status-danger-bg)',
    border: '1px solid var(--status-danger-border)',
  },
  alertBannerLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
  },
  alertTitle: {
    fontSize: '0.875rem',
    fontWeight: 600,
    color: 'var(--status-danger-text)',
  },
  alertDesc: {
    fontSize: '0.8rem',
    color: 'var(--status-danger-text)',
    marginTop: '0.15rem',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
    gap: '1.25rem',
  },
  counterCard: {
    display: 'flex',
    flexDirection: 'column',
    gap: '1rem',
  },
  cardHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  counterTitle: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.4rem',
    fontSize: '0.9rem',
  },
  statsRow: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '1rem',
  },
  statBlock: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.15rem',
  },
  statLabel: {
    fontSize: '0.75rem',
    color: 'var(--text-subtle)',
  },
  statVal: {
    fontSize: '1.35rem',
    fontWeight: 700,
    color: 'var(--text-main)',
  },
  statUnit: {
    fontSize: '0.75rem',
    fontWeight: 400,
    color: 'var(--text-subtle)',
  },
  queueViz: {
    paddingTop: '0.5rem',
    borderTop: '1px solid var(--border-subtle)',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.4rem',
  },
  vizLabel: {
    fontSize: '0.725rem',
    color: 'var(--text-subtle)',
  },
  dotsRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.4rem',
  },
  personDot: {
    width: '12px',
    height: '12px',
    borderRadius: '50%',
    transition: 'background-color 0.2s ease',
  },
  emptyCard: {
    gridColumn: '1 / -1',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    padding: '3rem',
    textAlign: 'center',
  },
};
