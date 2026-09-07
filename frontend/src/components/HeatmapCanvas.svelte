<script>
  import { onMount } from 'svelte';

  export let heatmapData = null;
  export let isLoading = false;

  let canvas;
  let hoveredCell = null;

  $: if (canvas && heatmapData && heatmapData.grid) {
    drawHeatmap();
  }

  function getHeatColor(val, max) {
    if (val <= 0 || max <= 0) return '#f8fafc';
    const ratio = Math.min(1.0, val / max);
    // Smooth thermal gradient: light-blue -> green -> yellow -> bright orange -> crimson
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

  function drawHeatmap() {
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
      hoveredCell = {
        r: row,
        c: col,
        val,
        x: Math.round(col * cell_size),
        y: Math.round(row * cell_size),
      };
      drawHeatmap();
    }
  }

  function handleMouseLeave() {
    hoveredCell = null;
    drawHeatmap();
  }

  onMount(() => {
    drawHeatmap();
  });
</script>

<div class="heatmap-container">
  <div class="heatmap-header">
    <div>
      <h3 class="section-title">Traffic & Dwell Heatmap</h3>
      <p class="section-desc">2D numeric accumulation of customer positions across the monitored camera viewport.</p>
    </div>
    {#if heatmapData}
      <div class="meta-badges">
        <span class="meta-badge">Grid: {heatmapData.rows}×{heatmapData.cols} ({heatmapData.cell_size}px)</span>
        <span class="meta-badge">Points: {heatmapData.total_points}</span>
        <span class="meta-badge">Viewport: {heatmapData.width}×{heatmapData.height}</span>
      </div>
    {/if}
  </div>

  <div class="canvas-wrapper">
    {#if isLoading && !heatmapData}
      <div class="placeholder">Loading heatmap data...</div>
    {:else if heatmapData && heatmapData.rows > 0}
      <canvas 
        bind:this={canvas} 
        width={heatmapData.width || 640} 
        height={heatmapData.height || 480}
        on:mousemove={handleMouseMove}
        on:mouseleave={handleMouseLeave}
      ></canvas>

      {#if hoveredCell}
        <div class="cell-tooltip">
          <span>Coordinate: <strong>({hoveredCell.x}px, {hoveredCell.y}px)</strong></span>
          <span>Grid: <strong>[{hoveredCell.r}, {hoveredCell.c}]</strong></span>
          <span>Intensity: <strong>{hoveredCell.val.toFixed(1)}</strong></span>
        </div>
      {/if}
    {:else}
      <div class="placeholder">No dwell heatmap data recorded.</div>
    {/if}
  </div>

  <div class="heatmap-legend">
    <span class="legend-label">Low Activity</span>
    <div class="legend-gradient"></div>
    <span class="legend-label">Peak Dwell Intensity</span>
  </div>
</div>

<style>
  .heatmap-container {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    box-shadow: var(--shadow-sm);
  }

  .heatmap-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
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

  .meta-badges {
    display: flex;
    gap: 0.4rem;
    flex-wrap: wrap;
  }

  .meta-badge {
    font-size: 0.72rem;
    font-family: var(--font-mono);
    padding: 0.2rem 0.5rem;
    background: #f1f5f9;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
  }

  .canvas-wrapper {
    position: relative;
    width: 100%;
    aspect-ratio: 4 / 3;
    max-height: 440px;
    background: #f8fafc;
    border-radius: var(--radius-md);
    border: 1px solid var(--border-color);
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  canvas {
    width: 100%;
    height: 100%;
    object-fit: contain;
    cursor: crosshair;
  }

  .cell-tooltip {
    position: absolute;
    bottom: 12px;
    left: 12px;
    background: #ffffff;
    border: 1px solid var(--border-color);
    padding: 0.4rem 0.8rem;
    border-radius: var(--radius-sm);
    font-size: 0.75rem;
    font-family: var(--font-mono);
    color: var(--text-secondary);
    display: flex;
    gap: 0.75rem;
    pointer-events: none;
    box-shadow: var(--shadow-md);
  }

  .cell-tooltip strong {
    color: var(--accent-blue);
  }

  .placeholder {
    color: var(--text-muted);
    font-size: 0.85rem;
  }

  .heatmap-legend {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding-top: 0.5rem;
  }

  .legend-label {
    font-size: 0.75rem;
    color: var(--text-muted);
    font-weight: 500;
  }

  .legend-gradient {
    flex: 1;
    height: 8px;
    border-radius: 4px;
    background: linear-gradient(to right, #e0f2fe, #6ee7b7, #fde047, #f97316, #dc2626);
    border: 1px solid var(--border-color);
  }
</style>
