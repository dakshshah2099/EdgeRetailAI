import React, { useState } from 'react';
import { Package, AlertCircle, CheckCircle2, AlertTriangle, Filter } from 'lucide-react';

export default function InventoryView({ stockEvents = [] }) {
  const [filterStatus, setFilterStatus] = useState('all'); // 'all' | 'depleted' | 'ok'

  const filteredEvents = stockEvents.filter((item) => {
    if (filterStatus === 'depleted') return item.status === 'low' || item.status === 'empty';
    if (filterStatus === 'ok') return item.status === 'ok';
    return true;
  });

  const depletedCount = stockEvents.filter(
    (s) => s.status === 'low' || s.status === 'empty'
  ).length;

  return (
    <div className="page-content">
      {/* Title & Filter Bar */}
      <div style={styles.titleBar}>
        <div>
          <h1>Shelf Inventory Health</h1>
          <p>ROI camera shelf vacancy classification & out-of-stock detection.</p>
        </div>

        {/* Filter Buttons */}
        <div style={styles.filterGroup}>
          <button
            onClick={() => setFilterStatus('all')}
            style={{
              ...styles.filterBtn,
              ...(filterStatus === 'all' ? styles.filterBtnActive : {}),
            }}
          >
            All Shelves ({stockEvents.length})
          </button>
          <button
            onClick={() => setFilterStatus('depleted')}
            style={{
              ...styles.filterBtn,
              ...(filterStatus === 'depleted' ? styles.filterBtnActiveDanger : {}),
            }}
          >
            Low / Empty ({depletedCount})
          </button>
          <button
            onClick={() => setFilterStatus('ok')}
            style={{
              ...styles.filterBtn,
              ...(filterStatus === 'ok' ? styles.filterBtnActive : {}),
            }}
          >
            Adequate Stock
          </button>
        </div>
      </div>

      {/* Shelves Grid */}
      <div style={styles.grid}>
        {filteredEvents.length > 0 ? (
          filteredEvents.map((shelf) => {
            const isDepleted = shelf.status === 'empty' || shelf.status === 'low';
            const statusClass =
              shelf.status === 'empty'
                ? 'badge badge-danger'
                : shelf.status === 'low'
                ? 'badge badge-warning'
                : 'badge badge-success';

            const statusText =
              shelf.status === 'empty'
                ? 'OUT OF STOCK'
                : shelf.status === 'low'
                ? 'LOW STOCK'
                : 'IN STOCK';

            const fillPercent =
              shelf.status === 'empty' ? 10 : shelf.status === 'low' ? 35 : 90;

            const fillColor =
              shelf.status === 'empty'
                ? '#ef4444'
                : shelf.status === 'low'
                ? '#f59e0b'
                : '#10b981';

            return (
              <div
                key={shelf.shelf_id}
                className="surface-card"
                style={{
                  ...styles.shelfCard,
                  borderColor: isDepleted
                    ? shelf.status === 'empty'
                      ? 'var(--status-danger-border)'
                      : 'var(--status-warning-border)'
                    : 'var(--border-subtle)',
                }}
              >
                <div style={styles.shelfTop}>
                  <div>
                    <div style={styles.shelfName}>
                      <Package size={16} color="#2563eb" />
                      <span>{shelf.shelf_id}</span>
                    </div>
                    <div style={styles.shelfCategory}>{shelf.category || 'Retail Goods'}</div>
                  </div>
                  <span className={statusClass}>{statusText}</span>
                </div>

                {/* Stock Level Bar */}
                <div style={styles.barContainer}>
                  <div style={styles.barLabelRow}>
                    <span style={styles.barLabel}>Estimated Capacity</span>
                    <strong style={{ fontSize: '0.8rem', color: fillColor }}>{fillPercent}%</strong>
                  </div>
                  <div style={styles.barTrack}>
                    <div
                      style={{
                        ...styles.barFill,
                        width: `${fillPercent}%`,
                        backgroundColor: fillColor,
                      }}
                    />
                  </div>
                </div>

                {/* Classifier Confidence & Timestamp */}
                <div style={styles.shelfMeta}>
                  <div style={styles.metaItem}>
                    <span>Edge Confidence:</span>
                    <strong>{shelf.confidence ? `${Math.round(shelf.confidence * 100)}%` : '96%'}</strong>
                  </div>
                  <div style={styles.metaItem}>
                    <span>Checked:</span>
                    <span>
                      {shelf.timestamp
                        ? new Date(shelf.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                        : 'Just now'}
                    </span>
                  </div>
                </div>
              </div>
            );
          })
        ) : (
          <div className="surface-card" style={styles.emptyCard}>
            <CheckCircle2 size={32} color="#059669" />
            <div style={{ marginTop: '0.5rem', fontWeight: 600 }}>All Monitored Shelves Stocked</div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-subtle)' }}>
              No replenishment actions required under current filter.
            </p>
          </div>
        )}
      </div>

      {/* Comprehensive Shelf Audit Table */}
      <section className="surface-card">
        <div style={{ marginBottom: '1rem' }}>
          <h2>Shelf Vacancy Classification Audit</h2>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-subtle)' }}>
            Latest on-device CV classifications by camera ROI
          </p>
        </div>

        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Shelf ID</th>
                <th>Category</th>
                <th>Status</th>
                <th>Inference Confidence</th>
                <th>Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {stockEvents.length > 0 ? (
                stockEvents.map((s) => (
                  <tr key={s.shelf_id}>
                    <td style={{ fontWeight: 600 }}>{s.shelf_id}</td>
                    <td>{s.category || 'General Shelf'}</td>
                    <td>
                      <span
                        className={
                          s.status === 'empty'
                            ? 'badge badge-danger'
                            : s.status === 'low'
                            ? 'badge badge-warning'
                            : 'badge badge-success'
                        }
                      >
                        {s.status.toUpperCase()}
                      </span>
                    </td>
                    <td>{s.confidence ? `${Math.round(s.confidence * 100)}%` : '95%'}</td>
                    <td style={{ color: 'var(--text-subtle)', fontSize: '0.8rem' }}>
                      {s.timestamp ? new Date(s.timestamp).toLocaleTimeString() : 'Recent'}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-subtle)' }}>
                    No shelf stock data detected.
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
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
    gap: '1.25rem',
  },
  shelfCard: {
    display: 'flex',
    flexDirection: 'column',
    gap: '1rem',
  },
  shelfTop: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
  },
  shelfName: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.4rem',
    fontSize: '0.925rem',
    fontWeight: 600,
    color: 'var(--text-main)',
  },
  shelfCategory: {
    fontSize: '0.75rem',
    color: 'var(--text-subtle)',
    marginTop: '0.15rem',
  },
  barContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.35rem',
  },
  barLabelRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '0.75rem',
  },
  barLabel: {
    color: 'var(--text-subtle)',
  },
  barTrack: {
    width: '100%',
    height: '6px',
    backgroundColor: '#f1f5f9',
    borderRadius: '9999px',
    overflow: 'hidden',
  },
  barFill: {
    height: '100%',
    borderRadius: '9999px',
    transition: 'width 0.3s ease',
  },
  shelfMeta: {
    paddingTop: '0.65rem',
    borderTop: '1px solid var(--border-subtle)',
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '0.75rem',
    color: 'var(--text-subtle)',
  },
  metaItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.35rem',
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
