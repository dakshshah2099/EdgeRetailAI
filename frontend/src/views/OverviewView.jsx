import React from 'react';
import KPICard from '../components/KPICard.jsx';
import { Users, Clock, Package, AlertTriangle, ArrowUpRight, CheckCircle2, AlertCircle, TrendingUp } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function OverviewView({
  footfallData,
  queueData = [],
  stockData = [],
  alertsData = [],
}) {
  const occupancy = footfallData ? footfallData.net_occupancy : 0;
  const totalEnters = footfallData ? footfallData.total_enters : 0;
  const totalExits = footfallData ? footfallData.total_exits : 0;
  const maxQueueLength = queueData.length
    ? Math.max(...queueData.map((q) => q.queue_length))
    : 0;
  const lowStockShelves = stockData.filter(
    (s) => s.status === 'empty' || s.status === 'low'
  ).length;
  const openAlerts = alertsData.filter((a) => !a.resolved_at);
  const openAlertsCount = openAlerts.length;

  const trendPoints = footfallData?.trend || [];
  const peakTraffic = trendPoints.length
    ? Math.max(...trendPoints.map((p) => p.enters || 0))
    : 0;

  return (
    <div className="page-content">
      {/* 1. Top KPI Summary Row - 5 bold glanceable cards */}
      <section style={styles.kpiGrid}>
        <KPICard
          title="Current In-Store"
          value={occupancy.toString()}
          subtitle={`Enters: ${totalEnters} • Exits: ${totalExits}`}
          icon="occupancy"
          tag="Live"
          status={occupancy > 30 ? 'warning' : 'normal'}
        />
        <KPICard
          title="Today's Footfall"
          value={totalEnters.toString()}
          subtitle="Total customer visits"
          icon="footfall"
          tag="Today"
          status="normal"
        />
        <KPICard
          title="Longest Queue"
          value={`${maxQueueLength} persons`}
          subtitle={`${queueData.length} active registers`}
          icon="queue"
          tag={maxQueueLength >= 4 ? 'Slow' : 'Fast'}
          status={maxQueueLength >= 4 ? 'danger' : 'success'}
        />
        <KPICard
          title="Restock Needed"
          value={`${lowStockShelves} shelves`}
          subtitle={`Of ${stockData.length} monitored`}
          icon="stock"
          tag={lowStockShelves > 0 ? 'Restock' : 'Stocked'}
          status={lowStockShelves > 0 ? 'warning' : 'success'}
        />
        <KPICard
          title="Active Notices"
          value={openAlertsCount.toString()}
          subtitle="Pending store action"
          icon="alerts"
          tag={openAlertsCount > 0 ? `${openAlertsCount} Open` : 'Clear'}
          status={openAlertsCount > 0 ? 'danger' : 'success'}
        />
      </section>

      {/* 2. Middle Row: Footfall Trend Curve (Left) + Immediate Action Alerts (Right) */}
      <div style={styles.middleGrid}>
        {/* Footfall Trend Curve */}
        <section className="surface-card" style={styles.trendSection}>
          <div style={styles.sectionHeader}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
              <h2>Customer Traffic Flow</h2>
              {peakTraffic > 0 && (
                <span className="badge badge-neutral" style={{ fontWeight: 700 }}>
                  Peak: {peakTraffic} shoppers/hr
                </span>
              )}
            </div>
            <Link to="/camera" style={styles.viewMoreLink}>
              <span>View Camera</span>
              <ArrowUpRight size={14} />
            </Link>
          </div>

          {trendPoints.length > 0 ? (
            <div style={styles.chartContainer}>
              <svg viewBox="0 0 800 130" style={styles.svgChart}>
                <defs>
                  <linearGradient id="trafficGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#2563eb" stopOpacity="0.22" />
                    <stop offset="100%" stopColor="#2563eb" stopOpacity="0.0" />
                  </linearGradient>
                </defs>
                <line x1="0" y1="20" x2="800" y2="20" stroke="#f1f5f9" strokeWidth="1" />
                <line x1="0" y1="65" x2="800" y2="65" stroke="#f1f5f9" strokeWidth="1" />
                <line x1="0" y1="110" x2="800" y2="110" stroke="#f1f5f9" strokeWidth="1" />

                {(() => {
                  const maxVal = Math.max(10, ...trendPoints.map((p) => Math.max(p.enters || 0, p.exits || 0)));
                  const coords = trendPoints.map((p, idx) => {
                    const x = (idx / Math.max(1, trendPoints.length - 1)) * 760 + 20;
                    const y = 115 - ((p.enters || 0) / maxVal) * 95;
                    return { x, y };
                  });
                  const pathD = coords.reduce(
                    (acc, pt, i) => (i === 0 ? `M ${pt.x} ${pt.y}` : `${acc} L ${pt.x} ${pt.y}`),
                    ''
                  );
                  const areaD = `${pathD} L ${coords[coords.length - 1].x} 125 L ${coords[0].x} 125 Z`;
                  return (
                    <>
                      <path d={areaD} fill="url(#trafficGradient)" />
                      <path d={pathD} fill="none" stroke="#2563eb" strokeWidth="3" />
                      {coords.map((pt, i) => (
                        <circle key={i} cx={pt.x} cy={pt.y} r="3.5" fill="#ffffff" stroke="#2563eb" strokeWidth="2.5" />
                      ))}
                    </>
                  );
                })()}
              </svg>
              <div style={styles.chartLabels}>
                {trendPoints.slice(0, 8).map((p, i) => (
                  <span key={i} style={styles.chartLabel}>
                    {p.timestamp ? new Date(p.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : `T-${i}`}
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <div style={styles.emptyNotice}>
              Footfall telemetry is recording incoming shoppers...
            </div>
          )}
        </section>

        {/* Immediate Store Alerts / Action Feed */}
        <section className="surface-card" style={styles.alertsSection}>
          <div style={styles.sectionHeader}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <h2>Immediate Attention</h2>
              {openAlertsCount > 0 && (
                <span className="badge badge-danger" style={{ fontWeight: 800 }}>
                  {openAlertsCount} ACTIVE
                </span>
              )}
            </div>
            <Link to="/alerts" style={styles.viewMoreLink}>
              <span>All Alerts</span>
              <ArrowUpRight size={14} />
            </Link>
          </div>

          <div style={styles.alertsScrollList}>
            {openAlerts.length > 0 ? (
              openAlerts.slice(0, 3).map((a) => {
                const isCritical = (a.severity || '').toLowerCase() === 'critical';
                const isWarning = (a.severity || '').toLowerCase() === 'warning';
                return (
                  <div
                    key={a.id || a.timestamp}
                    style={{
                      ...styles.alertMiniItem,
                      borderColor: isCritical
                        ? 'var(--status-danger-border)'
                        : isWarning
                        ? 'var(--status-warning-border)'
                        : 'var(--border-subtle)',
                      backgroundColor: isCritical
                        ? 'var(--status-danger-bg)'
                        : isWarning
                        ? 'var(--status-warning-bg)'
                        : 'var(--bg-subtle)',
                    }}
                  >
                    <div style={styles.alertMiniTop}>
                      {isCritical ? (
                        <AlertCircle size={15} color="#dc2626" strokeWidth={2.5} />
                      ) : (
                        <AlertTriangle size={15} color="#d97706" strokeWidth={2.5} />
                      )}
                      <strong style={styles.alertMiniType}>{a.alert_type || 'Notification'}</strong>
                      <span style={styles.alertMiniTime}>
                        {a.timestamp ? new Date(a.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Now'}
                      </span>
                    </div>
                    <div style={styles.alertMiniMsg}>{a.message}</div>
                  </div>
                );
              })
            ) : (
              <div style={styles.allClearNotice}>
                <CheckCircle2 size={24} color="#059669" strokeWidth={2.5} />
                <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#065f46' }}>
                  Store Operating Smoothly
                </span>
                <p style={{ fontSize: '0.725rem', color: 'var(--text-subtle)' }}>
                  No queue spillover or shelf vacancy warnings reported.
                </p>
              </div>
            )}
          </div>
        </section>
      </div>

      {/* 3. Bottom Row: Checkout Counters Load (Left) + Shelf Stock Depletion (Right) */}
      <div style={styles.twoColGrid}>
        {/* Checkout Counter Status */}
        <section className="surface-card">
          <div style={styles.sectionHeader}>
            <h2>Checkout Registers</h2>
            <Link to="/queues" style={styles.viewMoreLink}>
              <span>Manage Queues</span>
              <ArrowUpRight size={14} />
            </Link>
          </div>

          <div className="data-table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Counter</th>
                  <th>Current Queue</th>
                  <th>Est. Wait</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {queueData.length > 0 ? (
                  queueData.slice(0, 4).map((q) => {
                    const isCongested = q.queue_length >= 4;
                    return (
                      <tr key={q.counter_id}>
                        <td style={{ fontWeight: 700, color: 'var(--text-main)' }}>{q.counter_id}</td>
                        <td style={{ fontWeight: 700, fontSize: '0.9rem' }}>{q.queue_length} <span style={{ fontWeight: 400, fontSize: '0.75rem', color: 'var(--text-subtle)' }}>shoppers</span></td>
                        <td style={{ fontWeight: 600 }}>{q.avg_wait_seconds ? `${Math.round(q.avg_wait_seconds)}s` : '0s'}</td>
                        <td>
                          <span className={isCongested ? 'badge badge-danger' : 'badge badge-success'}>
                            {isCongested ? 'Congested' : 'Clear'}
                          </span>
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan="4" style={{ textAlign: 'center', color: 'var(--text-subtle)', padding: '1rem' }}>
                      All checkout counters are clear.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* Shelf Stock Depletion */}
        <section className="surface-card">
          <div style={styles.sectionHeader}>
            <h2>Shelf Stock Replenishment</h2>
            <Link to="/inventory" style={styles.viewMoreLink}>
              <span>All Shelves</span>
              <ArrowUpRight size={14} />
            </Link>
          </div>

          <div className="data-table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Shelf</th>
                  <th>Category</th>
                  <th>Capacity Level</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {stockData.length > 0 ? (
                  stockData.slice(0, 4).map((s) => {
                    const fillPercent = s.status === 'empty' ? 10 : s.status === 'low' ? 35 : 90;
                    const fillColor = s.status === 'empty' ? '#ef4444' : s.status === 'low' ? '#f59e0b' : '#10b981';

                    return (
                      <tr key={s.shelf_id}>
                        <td style={{ fontWeight: 700, color: 'var(--text-main)' }}>{s.shelf_id}</td>
                        <td style={{ color: 'var(--text-muted)', fontWeight: 500 }}>{s.category || 'Monitored'}</td>
                        <td style={{ minWidth: '120px' }}>
                          <div style={styles.miniBarContainer}>
                            <div style={styles.miniBarTrack}>
                              <div style={{ ...styles.miniBarFill, width: `${fillPercent}%`, backgroundColor: fillColor }} />
                            </div>
                            <span style={{ fontSize: '0.75rem', color: fillColor, fontWeight: 700 }}>{fillPercent}%</span>
                          </div>
                        </td>
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
                            {s.status === 'empty' ? 'RESTOCK NOW' : s.status === 'low' ? 'RESTOCK SOON' : 'OK'}
                          </span>
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan="4" style={{ textAlign: 'center', color: 'var(--text-subtle)', padding: '1rem' }}>
                      All monitored shelves adequately stocked.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}

const styles = {
  kpiGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
    gap: '0.75rem',
  },
  middleGrid: {
    display: 'grid',
    gridTemplateColumns: '1.6fr 1fr',
    gap: '1rem',
  },
  trendSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.5rem',
  },
  alertsSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.5rem',
  },
  sectionHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '0.25rem',
  },
  viewMoreLink: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.2rem',
    color: 'var(--accent-primary)',
    fontSize: '0.775rem',
    fontWeight: 700,
    textDecoration: 'none',
  },
  chartContainer: {
    width: '100%',
    display: 'flex',
    flexDirection: 'column',
  },
  svgChart: {
    width: '100%',
    height: '110px',
    overflow: 'visible',
  },
  chartLabels: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '0.25rem 0.25rem 0',
  },
  chartLabel: {
    fontSize: '0.7rem',
    fontWeight: 600,
    color: 'var(--text-subtle)',
  },
  emptyNotice: {
    padding: '1.5rem',
    textAlign: 'center',
    color: 'var(--text-subtle)',
    fontSize: '0.8rem',
  },
  alertsScrollList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.5rem',
    flex: 1,
    justifyContent: 'center',
  },
  alertMiniItem: {
    padding: '0.6rem 0.75rem',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid transparent',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.2rem',
  },
  alertMiniTop: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.4rem',
  },
  alertMiniType: {
    fontSize: '0.775rem',
    color: 'var(--text-main)',
    fontWeight: 700,
    flex: 1,
  },
  alertMiniTime: {
    fontSize: '0.7rem',
    fontWeight: 600,
    color: 'var(--text-subtle)',
  },
  alertMiniMsg: {
    fontSize: '0.75rem',
    color: 'var(--text-muted)',
    lineHeight: 1.35,
  },
  allClearNotice: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '1.5rem',
    gap: '0.35rem',
    textAlign: 'center',
  },
  twoColGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
    gap: '1rem',
  },
  miniBarContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
  },
  miniBarTrack: {
    flex: 1,
    height: '6px',
    backgroundColor: '#f1f5f9',
    borderRadius: '9999px',
    overflow: 'hidden',
  },
  miniBarFill: {
    height: '100%',
    borderRadius: '9999px',
  },
};
