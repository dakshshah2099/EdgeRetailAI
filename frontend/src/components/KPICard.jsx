import React from 'react';
import { Users, TrendingUp, Clock, Package, AlertTriangle } from 'lucide-react';

const ICON_MAP = {
  occupancy: { icon: Users, color: '#2563eb', bg: '#eff6ff' },
  footfall: { icon: TrendingUp, color: '#059669', bg: '#ecfdf5' },
  queue: { icon: Clock, color: '#d97706', bg: '#fffbeb' },
  stock: { icon: Package, color: '#7c3aed', bg: '#f5f3ff' },
  alerts: { icon: AlertTriangle, color: '#dc2626', bg: '#fef2f2' },
};

export default function KPICard({
  title,
  value,
  subtitle,
  icon = 'occupancy',
  status = 'normal',
  tag,
}) {
  const conf = ICON_MAP[icon] || { icon: Users, color: '#2563eb', bg: '#eff6ff' };
  const IconComponent = conf.icon;

  const getStatusBadge = () => {
    switch (status) {
      case 'danger':
        return 'badge badge-danger';
      case 'warning':
        return 'badge badge-warning';
      case 'success':
        return 'badge badge-success';
      default:
        return 'badge badge-neutral';
    }
  };

  return (
    <div style={styles.card}>
      <div style={styles.headerRow}>
        <div style={{ ...styles.iconContainer, backgroundColor: conf.bg }}>
          <IconComponent size={17} color={conf.color} strokeWidth={2.2} />
        </div>
        {tag && <span className={getStatusBadge()}>{tag}</span>}
      </div>

      <div style={styles.content}>
        <div style={styles.value}>{value}</div>
        <div style={styles.title}>{title}</div>
        {subtitle && <div style={styles.subtitle}>{subtitle}</div>}
      </div>
    </div>
  );
}

const styles = {
  card: {
    backgroundColor: 'var(--bg-surface)',
    border: '1px solid var(--border-subtle)',
    borderRadius: 'var(--radius-md)',
    boxShadow: 'var(--shadow-xs)',
    padding: '0.85rem 1rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.55rem',
    transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
  },
  headerRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  iconContainer: {
    width: '30px',
    height: '30px',
    borderRadius: 'var(--radius-sm)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  content: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.1rem',
  },
  value: {
    fontSize: '1.65rem',
    fontWeight: 800,
    color: 'var(--text-main)',
    lineHeight: 1.15,
    letterSpacing: '-0.035em',
    fontVariantNumeric: 'tabular-nums',
  },
  title: {
    fontSize: '0.8rem',
    fontWeight: 700,
    color: 'var(--text-main)',
  },
  subtitle: {
    fontSize: '0.7rem',
    fontWeight: 500,
    color: 'var(--text-subtle)',
    marginTop: '0.05rem',
  },
};
