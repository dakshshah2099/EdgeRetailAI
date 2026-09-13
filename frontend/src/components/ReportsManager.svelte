<script>
  import { getDailyReportDownloadUrl } from "../lib/api.js";

  let selectedDate = $state(new Date().toISOString().slice(0, 10));
  let isDownloading = $state(false);
  let statusMsg = $state("");
  let isError = $state(false);

  async function triggerDownload(format) {
    if (!selectedDate) return;
    isDownloading = true;
    statusMsg = `Generating ${format.toUpperCase()} report for ${selectedDate}...`;
    isError = false;

    try {
      const url = getDailyReportDownloadUrl(selectedDate, format);
      const res = await fetch(url);
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || "Report generation failed");
      }
      const blob = await res.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = `daily_report_${selectedDate}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(downloadUrl);

      statusMsg = `✓ Successfully downloaded daily_report_${selectedDate}.${format}`;
      isError = false;
    } catch (err) {
      statusMsg = `Error: ${err.message}`;
      isError = true;
    } finally {
      isDownloading = false;
    }
  }
</script>

<div class="bg-white border border-slate-200 rounded-lg p-4 sm:p-6 shadow-xs flex flex-col gap-5">
  <div class="flex items-center justify-between flex-wrap gap-2 pb-3 border-b border-slate-100">
    <div>
      <h3 class="text-base font-semibold text-slate-900">Automated Analytics Reports</h3>
      <p class="text-xs text-slate-500 font-mono mt-0.5">
        Export comprehensive daily store activity snapshots to CSV or PDF
      </p>
    </div>
  </div>

  <div class="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
    <div class="bg-slate-50 border border-slate-200 rounded-md p-4 flex flex-col gap-4">
      <div class="flex flex-col gap-1.5">
        <label for="report-date" class="text-xs font-mono font-semibold text-slate-700 uppercase">
          Select Report Date
        </label>
        <input
          id="report-date"
          type="date"
          class="px-3 py-2 text-sm bg-white border border-slate-300 rounded-md focus:outline-none focus:ring-1 focus:ring-sky-500"
          bind:value={selectedDate}
        />
        <p class="text-[11px] font-mono text-slate-500">
          Aggregates all footfall, queue lengths, inventory depletions, and alert response times for [00:00, 23:59:59).
        </p>
      </div>

      <div class="flex items-center gap-3 pt-2">
        <button
          type="button"
          class="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-sky-600 hover:bg-sky-700 text-white text-xs font-semibold rounded-md shadow-xs cursor-pointer transition-colors disabled:opacity-50"
          onclick={() => triggerDownload("csv")}
          disabled={isDownloading || !selectedDate}
        >
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          Download CSV
        </button>

        <button
          type="button"
          class="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold rounded-md shadow-xs cursor-pointer transition-colors disabled:opacity-50"
          onclick={() => triggerDownload("pdf")}
          disabled={isDownloading || !selectedDate}
        >
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
            <polyline points="10 9 9 9 8 9"/>
          </svg>
          Download PDF
        </button>
      </div>

      {#if statusMsg}
        <div class="p-2.5 rounded text-xs font-mono {isError ? 'bg-rose-50 text-rose-800 border border-rose-200' : 'bg-emerald-50 text-emerald-800 border border-emerald-200'}">
          {statusMsg}
        </div>
      {/if}
    </div>

    <!-- Features Overview -->
    <div class="flex flex-col gap-3 text-xs text-slate-600">
      <h4 class="font-mono font-semibold text-slate-700 uppercase">Included Audit Sections</h4>
      <div class="space-y-2 font-mono">
        <div class="p-2.5 rounded border border-slate-200 bg-white">
          <strong class="text-slate-900">1. Store Flow & Footfall:</strong> Total enters, exits, net occupancy, and peak traffic hours.
        </div>
        <div class="p-2.5 rounded border border-slate-200 bg-white">
          <strong class="text-slate-900">2. Register Queues:</strong> Counter line lengths, estimated wait times, and bottleneck alerts.
        </div>
        <div class="p-2.5 rounded border border-slate-200 bg-white">
          <strong class="text-slate-900">3. Shelf Depletions:</strong> Stock levels, replenishment alerts, and planogram facing status.
        </div>
        <div class="p-2.5 rounded border border-slate-200 bg-white">
          <strong class="text-slate-900">4. Staff Efficiency:</strong> Alert resolution speed, active counter metrics, and recommendation follow rates.
        </div>
      </div>
    </div>
  </div>
</div>
