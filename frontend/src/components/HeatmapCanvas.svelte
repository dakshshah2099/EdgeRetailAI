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
    // Crisp light thermal spectrum: light-sky -> emerald -> amber -> deep-crimson
    if (ratio < 0.25) {
      const t = ratio / 0.25;
      return `rgba(56, 189, 248, ${0.2 + 0.3 * t})`; // Sky blue
    } else if (ratio < 0.5) {
      const t = (ratio - 0.25) / 0.25;
      return `rgba(16, 185, 129, ${0.4 + 0.3 * t})`; // Emerald
    } else if (ratio < 0.75) {
      const t = (ratio - 0.5) / 0.25;
      return `rgba(245, 158, 11, ${0.6 + 0.3 * t})`; // Amber
    } else {
      const t = (ratio - 0.75) / 0.25;
      return `rgba(225, 29, 72, ${0.75 + 0.25 * t})`; // Crimson
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

    ctx.fillStyle = '#f8fafc';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw Heat Cells
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const val = grid[r] ? grid[r][c] || 0 : 0;
        ctx.fillStyle = getHeatColor(val, maxVal);
        ctx.fillRect(c * cellW, r * cellH, cellW, cellH);

        // Technical gridlines
        ctx.strokeStyle = 'rgba(226, 232, 240, 0.8)';
        ctx.lineWidth = 0.5;
        ctx.strokeRect(c * cellW, r * cellH, cellW, cellH);
      }
    }
  }

  function handleMouseMove(e) {
    if (!canvas || !heatmapData || !heatmapData.grid) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const { rows, cols, grid } = heatmapData;
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    const c = Math.floor((x * scaleX) / (canvas.width / cols));
    const r = Math.floor((y * scaleY) / (canvas.height / rows));

    if (r >= 0 && r < rows && c >= 0 && c < cols) {
      hoveredCell = { row: r, col: c, dwell_seconds: grid[r] ? grid[r][c] || 0 : 0 };
    }
  }

  function handleMouseLeave() {
    hoveredCell = null;
  }
</script>

<div class="bg-white border border-slate-200 rounded-md p-4 flex flex-col gap-3 shadow-xs">
  <!-- Header -->
  <div class="flex items-center justify-between flex-wrap gap-2 pb-2 border-b border-slate-100">
    <div>
      <div class="flex items-center gap-2">
        <span class="text-sm font-semibold uppercase tracking-wider text-slate-900">Spatial Dwell Heatmap</span>
        <span class="px-1.5 py-0.5 text-xs font-mono bg-sky-50 text-sky-700 border border-sky-200 rounded">
          SPATIAL ROI
        </span>
      </div>
      <p class="text-xs text-slate-500 font-mono mt-0.5">Aggregated dwell time density across camera tracking perspective.</p>
    </div>

    <!-- Thermal Spectrum Legend -->
    <div class="flex items-center gap-2 text-xs font-mono text-slate-500">
      <span>MIN (0s)</span>
      <div class="w-24 h-2 rounded-sm bg-gradient-to-r from-sky-200 via-emerald-400 via-amber-400 to-rose-500 border border-slate-200"></div>
      <span>MAX DWELL</span>
    </div>
  </div>

  <!-- Heatmap Canvas Stage -->
  <div class="relative w-full aspect-video bg-slate-50 border border-slate-200 rounded-md overflow-hidden flex items-center justify-center">
    <canvas
      bind:this={canvas}
      width={640}
      height={480}
      class="w-full h-full object-contain cursor-crosshair"
      on:mousemove={handleMouseMove}
      on:mouseleave={handleMouseLeave}
    ></canvas>

    {#if isLoading}
      <div class="absolute inset-0 bg-white/70 backdrop-blur-xs flex items-center justify-center font-mono text-xs text-sky-700 gap-2">
        <span class="w-2 h-2 rounded-full bg-sky-600 animate-ping"></span>
        <span>UPDATING SPATIAL MATRIX...</span>
      </div>
    {/if}

    <!-- Inspection Reticle / Tooltip -->
    {#if hoveredCell}
      <div class="absolute bottom-2 left-2 bg-white/95 border border-slate-200 px-2.5 py-1 text-xs font-mono text-slate-800 rounded shadow-md">
        GRID [R{hoveredCell.row}, C{hoveredCell.col}]: <strong class="text-sky-700">{Math.round(hoveredCell.dwell_seconds)}s</strong> DWELL
      </div>
    {/if}
  </div>

  <div class="flex items-center justify-between text-xs font-mono text-slate-500 pt-1">
    <span>Resolution: {heatmapData?.rows || 16} × {heatmapData?.cols || 16} cells</span>
    <span>Zero raw frames stored • Anonymized vectors only</span>
  </div>
</div>
