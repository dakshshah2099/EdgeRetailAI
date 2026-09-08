import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Video,
  Activity,
  Users,
  Package,
  Bell,
  Settings,
  ShieldCheck,
  Store,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

export default function Sidebar({
  openAlertsCount = 0,
  isConnected = true,
  isCollapsed = false,
  onToggleCollapse,
}) {
  const monitoringGroup = [
    { to: '/overview', label: 'Store Overview', icon: LayoutDashboard },
    { to: '/camera', label: 'Live Camera', icon: Video },
    { to: '/heatmap', label: 'Customer Dwell', icon: Activity },
  ];

  const managementGroup = [
    { to: '/queues', label: 'Checkout Queues', icon: Users },
    { to: '/inventory', label: 'Shelf Stock', icon: Package },
    { to: '/alerts', label: 'Alerts', icon: Bell, badge: openAlertsCount },
    { to: '/settings', label: 'Settings', icon: Settings },
  ];

  const renderNavItem = (item) => {
    const Icon = item.icon;
    return (
      <NavLink
        key={item.to}
        to={item.to}
        title={isCollapsed ? item.label : undefined}
        style={({ isActive }) => ({
          ...styles.navLink,
          ...(isCollapsed ? styles.navLinkCollapsed : styles.navLinkExpanded),
          ...(isActive ? styles.navLinkActive : {}),
        })}
      >
        <div style={styles.iconWrapper}>
          <Icon size={18} strokeWidth={2} />
          {isCollapsed && item.badge > 0 && (
            <span style={styles.badgeDot} />
          )}
        </div>
        {!isCollapsed && (
          <>
            <span style={styles.navLabel}>{item.label}</span>
            {item.badge > 0 && (
              <span className="badge badge-danger" style={styles.alertBadge}>
                {item.badge}
              </span>
            )}
          </>
        )}
      </NavLink>
    );
  };

  return (
    <aside
      style={{
        ...styles.sidebar,
        width: isCollapsed
          ? 'var(--sidebar-width-collapsed)'
          : 'var(--sidebar-width-expanded)',
      }}
      aria-label="Main Navigation"
    >
      {/* Brand Header */}
      <div style={isCollapsed ? styles.brandCollapsed : styles.brandExpanded}>
        {!isCollapsed ? (
          <>
            <div style={styles.brandLeft}>
              <div style={styles.brandIconWrapper} title="Retail Intelligence">
                <Store size={18} color="#2563eb" />
              </div>
              <div style={styles.brandTitles}>
                <div style={styles.brandTitle}>StoreOps</div>
                <div style={styles.brandSubtitle}>Retail Intelligence</div>
              </div>
            </div>
            <button
              onClick={onToggleCollapse}
              style={styles.collapseBtn}
              title="Collapse sidebar"
              aria-label="Collapse sidebar"
            >
              <ChevronLeft size={15} />
            </button>
          </>
        ) : (
          <button
            onClick={onToggleCollapse}
            style={styles.expandBtnCollapsed}
            title="Expand sidebar"
            aria-label="Expand sidebar"
          >
            <Store size={18} color="#2563eb" />
            <ChevronRight size={12} color="#64748b" style={{ marginTop: '2px' }} />
          </button>
        )}
      </div>

      {/* Structured Navigation Groups */}
      <nav style={styles.nav}>
        {/* Monitoring Group */}
        <div style={styles.group}>
          {!isCollapsed && <div style={styles.groupLabel}>MONITORING</div>}
          <div style={styles.groupItems}>
            {monitoringGroup.map(renderNavItem)}
          </div>
        </div>

        {/* Separator */}
        <div style={styles.divider} />

        {/* Management Group */}
        <div style={styles.group}>
          {!isCollapsed && <div style={styles.groupLabel}>MANAGEMENT</div>}
          <div style={styles.groupItems}>
            {managementGroup.map(renderNavItem)}
          </div>
        </div>
      </nav>

      {/* Footer Info */}
      <div style={isCollapsed ? styles.footerCollapsed : styles.footerExpanded}>
        <div
          style={styles.securityBadge}
          title="Customer Privacy Protected • No Personal Data Stored"
        >
          <ShieldCheck size={16} color="#059669" />
          {!isCollapsed && <span style={styles.securityText}>Privacy Protected</span>}
        </div>
      </div>
    </aside>
  );
}

const styles = {
  sidebar: {
    backgroundColor: 'var(--bg-sidebar)',
    borderRight: '1px solid var(--border-subtle)',
    display: 'flex',
    flexDirection: 'column',
    flexShrink: 0,
    minHeight: '100vh',
    userSelect: 'none',
    overflow: 'hidden',
  },
  brandExpanded: {
    height: 'var(--header-height)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 1rem',
    borderBottom: '1px solid var(--border-subtle)',
  },
  brandCollapsed: {
    height: 'var(--header-height)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderBottom: '1px solid var(--border-subtle)',
  },
  brandLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.65rem',
  },
  brandIconWrapper: {
    width: '32px',
    height: '32px',
    borderRadius: 'var(--radius-sm)',
    backgroundColor: 'var(--accent-primary-subtle)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  brandTitles: {
    display: 'flex',
    flexDirection: 'column',
  },
  brandTitle: {
    fontSize: '0.925rem',
    fontWeight: 700,
    color: 'var(--text-main)',
    lineHeight: 1.2,
    letterSpacing: '-0.02em',
  },
  brandSubtitle: {
    fontSize: '0.7rem',
    color: 'var(--text-subtle)',
  },
  collapseBtn: {
    width: '26px',
    height: '26px',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border-subtle)',
    backgroundColor: 'var(--bg-surface)',
    color: 'var(--text-muted)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    flexShrink: 0,
    transition: 'background-color 0.15s ease, color 0.15s ease',
  },
  expandBtnCollapsed: {
    width: '36px',
    height: '36px',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border-subtle)',
    backgroundColor: 'var(--bg-muted)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    padding: '2px',
  },
  nav: {
    flex: 1,
    padding: '0.85rem 0.5rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.5rem',
  },
  group: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.15rem',
  },
  groupLabel: {
    fontSize: '0.65rem',
    fontWeight: 700,
    color: 'var(--text-subtle)',
    letterSpacing: '0.06em',
    padding: '0.2rem 0.65rem 0.35rem',
  },
  groupItems: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.2rem',
  },
  divider: {
    height: '1px',
    backgroundColor: 'var(--border-subtle)',
    margin: '0.25rem 0.5rem',
  },
  navLink: {
    display: 'flex',
    alignItems: 'center',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--text-muted)',
    textDecoration: 'none',
    fontSize: '0.825rem',
    fontWeight: 500,
    position: 'relative',
    transition: 'background-color 0.15s ease, color 0.15s ease',
  },
  navLinkExpanded: {
    gap: '0.65rem',
    padding: '0.55rem 0.75rem',
    justifyContent: 'flex-start',
  },
  navLinkCollapsed: {
    width: '42px',
    height: '40px',
    margin: '0 auto',
    justifyContent: 'center',
    padding: 0,
  },
  navLinkActive: {
    backgroundColor: 'var(--accent-primary-subtle)',
    color: 'var(--accent-primary-text)',
    fontWeight: 700,
    border: '1px solid #bfdbfe',
  },
  iconWrapper: {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  badgeDot: {
    position: 'absolute',
    top: '-3px',
    right: '-3px',
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    backgroundColor: '#dc2626',
    border: '1.5px solid #ffffff',
  },
  navLabel: {
    flex: 1,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  alertBadge: {
    padding: '0.1rem 0.45rem',
    fontSize: '0.675rem',
  },
  footerExpanded: {
    padding: '0.75rem 1rem',
    borderTop: '1px solid var(--border-subtle)',
    backgroundColor: 'var(--bg-subtle)',
  },
  footerCollapsed: {
    padding: '0.75rem 0',
    display: 'flex',
    justifyContent: 'center',
    borderTop: '1px solid var(--border-subtle)',
    backgroundColor: 'var(--bg-subtle)',
  },
  securityBadge: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.4rem',
    fontSize: '0.75rem',
    color: '#065f46',
    fontWeight: 600,
  },
  securityText: {
    fontSize: '0.725rem',
    whiteSpace: 'nowrap',
  },
};
