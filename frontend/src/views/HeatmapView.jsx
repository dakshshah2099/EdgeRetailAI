import React, { useRef, useEffect, useState } from 'react';
import { Activity, Info, MapPin } from 'lucide-react';

export default function HeatmapView({ heatmapData, isLoading = false }) {
  const canvasRef = useRef(null);
  const [hoveredCell, setHoveredCell] = useState(null);

  function getHeatColor(val, max) {
    if (val <= 0 || max <= 0) return '#f8fafc';
    const ratio = Math.min(1.0, val / max);
    if (ratio < 0.25) {
      const t = ratio / 0.25;
      return `rgb(${Math.round(224 * (1 - t) + 147 * t)}, ${Math.round(242 * (1 - t) + 197 * t)}, ${Math.round(254 * (1 - t) + 253 * t)})`;
    } else if (ratio < 0.5) {
      const t = (ratio - 0.25) / 0.25;
      return `rgb(${Math.round(147 * (1 - t) + 110 * t)}, ${Math.round(197 * (1 - t) + 231 * t)}, ${Math.round(253 * (1 - t) + 183 * t)})`;
    } else if (ratio < 0.75) {
      const t = (ratio - 0.5) / 0.25;
      return `rgb(${Math.round(110 * (1 - t) + 251 * t)}, ${Math.round(231 * (1 - t) + 191 * t)}, ${Math.round(183 * (1 - t) + 36 * t)})`;
    } else {
      const t = (ratio - 0.75) / 0.25;
      return `rgb(${Math.round(251 * (1 - t) + 220 * t)}, ${Math.round(191 * (1 - t) + 38 * t)}, ${Math.round(36 * (1 - t) + 38 * t)})`;
    }
  }

  useEffect(() => {
    drawHeatmap();
  }, [heatmapData, hoveredCell]);

  function drawHeatmap() {
    const canvas = canvasRef.current;
    if (!canvas || !heatmapData || !heatmapData.grid) return;
    const ctx = canvas.getContext('2d');
    const { grid, rows, cols } = heatmapData;

    if (!rows || !cols || !grid.length) return;

    let maxVal = 0;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        if (grid[r] && grid[r][c] > maxVal) {
          maxVal = grid[r][c];
        }
      }
    }
    if (maxVal === 0) maxVal = 1;

    const cellW = canvas.width / cols;
    const cellH = canvas.height / rows;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const val = grid[r] ? grid[r][c] || 0 : 0;
        ctx.fillStyle = getHeatColor(val, maxVal);
        ctx.fillRect(c * cellW, r * cellH, cellW, cellH);

        ctx.strokeStyle = '#e2e8f0';
        ctx.lineWidth = 0.5;
        ctx.strokeRect(c * cellW, r * cellH, cellW, cellH);
      }
    }

    if (hoveredCell && hoveredCell.r < rows && hoveredCell.c < cols) {
      ctx.strokeStyle = '#2563eb';
      ctx.lineWidth = 2;
      ctx.strokeRect(hoveredCell.c * cellW, hoveredCell.r * cellH, cellW, cellH);
    }
  }

  function handleMouseMove(e) {
    const canvas = canvasRef.current;
    if (!canvas || !heatmapData) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const { rows, cols, grid, cell_size } = heatmapData;
    const cellW = rect.width / cols;
    const cellH = rect.height / rows;

    const col = Math.floor(x / cellW);
    const row = Math.floor(y / cellH);

    if (row >= 0 && row < rows && col >= 0 && col < cols) {
      const val = grid[row] ? grid[row][col] || 0 : 0;
      setHoveredCell({
        r: row,
        c: col,
        val,
        x: Math.round(col * cell_size),
        y: Math.round(row * cell_size),
      });
    }
  }

  function handleMouseLeave() {
    setHoveredCell(null);
  }

  const rows = heatmapData?.rows || 0;
  const cols = heatmapData?.cols || 0;
  const cellSize = heatmapData?.cell_size || 32;

  let totalDwellTicks = 0;
  let maxDwellVal = 0;
  if (heatmapData?.grid) {
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const v = heatmapData.grid[r]?.[c] || 0;
        totalDwellTicks += v;
        if (v > maxDwellVal) maxDwellVal = v;
      }
    }
  }

  return (
    <div className="page-content">
      {/* Title */}
      <div style={styles.titleBar}>
        <div>
          <h1>Traffic & Dwell Heatmap</h1>
          <p>Spatial 2D floor dwell density dynamically mapped to camera viewport.</p>
        </div>

        {/* Aggregate Stats Pill */}
        <div style={styles.statsPill}>
          <div style={styles.statItem}>
            <span style={styles.statLabel}>Resolution:</span>
            <span style={styles.statVal}>{cols}x{rows} ({cellSize}px)</span>
          </div>
          <span style={styles.divider}>|</span>
          <div style={styles.statItem}>
            <span style={styles.statLabel}>Peak Intensity:</span>
            <span style={styles.statVal}>{maxDwellVal} hits</span>
          </div>
        </div>
      </div>

      {/* Heatmap Card */}
      <div className="surface-card" style={styles.canvasCard}>
        <div style={styles.canvasWrapper}>
          <canvas
            ref={canvasRef}
            width={800}
            height={500}
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
            style={styles.canvas}
          />
        </div>

        {/* Legend & Hover Data Bar */}
        <div style={styles.legendBar}>
          {/* Gradient Legend */}
          <div style={styles.legendGroup}>
            <span style={styles.legendLabel}>Low Dwell</span>
            <div style={styles.gradientBar} />
            <span style={styles.legendLabel}>High Dwell</span>
          </div>

          {/* Hovered Cell Inspector */}
          <div style={styles.hoverInspector}>
            {hoveredCell ? (
              <div style={styles.cellInfo}>
                <MapPin size={14} color="#2563eb" />
                <span>
                  Grid [{hoveredCell.c}, {hoveredCell.r}] • Dwell Density: <strong>{hoveredCell.val}</strong>
                </span>
              </div>
            ) : (
              <span style={styles.hoverPlaceholder}>
                Hover over grid to inspect local dwell coordinates
              </span>
            )}
          </div>
        </div>
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
  statsPill: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
    padding: '0.4rem 0.85rem',
    borderRadius: 'var(--radius-sm)',
    backgroundColor: 'var(--bg-surface)',
    border: '1px solid var(--border-subtle)',
    fontSize: '0.8rem',
  },
  statItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.35rem',
  },
  statLabel: {
    color: 'var(--text-subtle)',
  },
  statVal: {
    fontWeight: 600,
    color: 'var(--text-main)',
  },
  divider: {
    color: 'var(--border-subtle)',
  },
  canvasCard: {
    padding: '1.25rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '1rem',
  },
  canvasWrapper: {
    width: '100%',
    display: 'flex',
    justifyContent: 'center',
    backgroundColor: '#f8fafc',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border-subtle)',
    overflow: 'hidden',
  },
  canvas: {
    maxWidth: '100%',
    height: 'auto',
    cursor: 'crosshair',
    display: 'block',
  },
  legendBar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: '0.5rem',
  },
  legendGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
  },
  legendLabel: {
    fontSize: '0.75rem',
    color: 'var(--text-subtle)',
  },
  gradientBar: {
    width: '140px',
    height: '10px',
    borderRadius: '9999px',
    background: 'linear-gradient(to right, rgb(224, 242, 254), rgb(110, 231, 183), rgb(251, 191, 36), rgb(220, 38, 38))',
    border: '1px solid var(--border-subtle)',
  },
  hoverInspector: {
    fontSize: '0.8rem',
    color: 'var(--text-muted)',
  },
  cellInfo: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.4rem',
  },
  hoverPlaceholder: {
    color: 'var(--text-subtle)',
    fontSize: '0.775rem',
  },
};
