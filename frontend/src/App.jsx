import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/Sidebar.jsx';
import Header from './components/Header.jsx';
import OverviewView from './views/OverviewView.jsx';
import CameraView from './views/CameraView.jsx';
import HeatmapView from './views/HeatmapView.jsx';
import QueuesView from './views/QueuesView.jsx';
import InventoryView from './views/InventoryView.jsx';
import AlertsView from './views/AlertsView.jsx';
import SettingsView from './views/SettingsView.jsx';
import {
  fetchKPIFootfall,
  fetchKPIQueue,
  fetchKPIStock,
  fetchAlerts,
  fetchHeatmap,
  fetchSystemEnv,
  checkHealth,
} from './lib/api.js';

export default function App() {
  const [isConnected, setIsConnected] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(new Date());
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshIntervalSec, setRefreshIntervalSec] = useState(3);

  // Collapsible sidebar state
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return localStorage.getItem('sidebar_collapsed') === 'true';
    } catch {
      return false;
    }
  });

  const handleToggleSidebar = () => {
    setSidebarCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem('sidebar_collapsed', String(next));
      } catch {}
      return next;
    });
  };

  // Filters
  const [selectedTimeRange, setSelectedTimeRange] = useState('all');
  const [selectedZone, setSelectedZone] = useState('');
  const [alertFilter, setAlertFilter] = useState('open');

  // Data Store
  const [footfallData, setFootfallData] = useState(null);
  const [queueData, setQueueData] = useState([]);
  const [stockData, setStockData] = useState([]);
  const [alertsData, setAlertsData] = useState([]);
  const [heatmapData, setHeatmapData] = useState(null);

  // Debug & System Env
  const [debugMode, setDebugMode] = useState(false);
  const [envVariables, setEnvVariables] = useState({});

  const timerRef = useRef(null);

  function getSinceISO(range) {
    const now = new Date();
    if (range === '1h') return new Date(now.getTime() - 3600 * 1000).toISOString();
    if (range === '6h') return new Date(now.getTime() - 6 * 3600 * 1000).toISOString();
    if (range === '24h') return new Date(now.getTime() - 24 * 3600 * 1000).toISOString();
    return null;
  }

  const loadAllData = useCallback(async () => {
    setIsRefreshing(true);
    const since = getSinceISO(selectedTimeRange);
    const params = {
      zone_id: selectedZone || null,
      since: since || null,
    };

    try {
      const [healthy, footfall, queue, stock, alerts, heatmap, sysEnv] =
        await Promise.allSettled([
          checkHealth(),
          fetchKPIFootfall({ ...params, group_by: 'hour' }),
          fetchKPIQueue(),
          fetchKPIStock(),
          fetchAlerts({ status: alertFilter }),
          fetchHeatmap(params),
          fetchSystemEnv(),
        ]);

      setIsConnected(healthy.status === 'fulfilled' && healthy.value);
      if (footfall.status === 'fulfilled') setFootfallData(footfall.value);
      if (queue.status === 'fulfilled') setQueueData(queue.value || []);
      if (stock.status === 'fulfilled') setStockData(stock.value || []);
      if (alerts.status === 'fulfilled') setAlertsData(alerts.value || []);
      if (heatmap.status === 'fulfilled') setHeatmapData(heatmap.value);
      if (sysEnv.status === 'fulfilled') {
        setDebugMode(sysEnv.value.debug_mode || false);
        setEnvVariables(sysEnv.value.variables || {});
      }

      setLastUpdated(new Date());
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
      setIsConnected(false);
    } finally {
      setIsRefreshing(false);
    }
  }, [selectedTimeRange, selectedZone, alertFilter]);

  // Polling setup
  useEffect(() => {
    loadAllData();
  }, [loadAllData]);

  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (autoRefresh && refreshIntervalSec > 0) {
      timerRef.current = setInterval(() => {
        loadAllData();
      }, refreshIntervalSec * 1000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [autoRefresh, refreshIntervalSec, loadAllData]);

  const openAlertsCount = alertsData.filter((a) => !a.resolved_at).length;

  return (
    <div className="app-container">
      {/* Collapsible Persistent Left Sidebar */}
      <Sidebar
        openAlertsCount={openAlertsCount}
        isConnected={isConnected}
        isCollapsed={sidebarCollapsed}
        onToggleCollapse={handleToggleSidebar}
      />

      {/* Main Content Area */}
      <div className="app-main">
        <Header
          isConnected={isConnected}
          isRefreshing={isRefreshing}
          lastUpdated={lastUpdated}
          openAlertsCount={openAlertsCount}
          refreshIntervalSec={refreshIntervalSec}
          selectedTimeRange={selectedTimeRange}
          selectedZone={selectedZone}
          onTimeRangeChange={setSelectedTimeRange}
          onZoneChange={setSelectedZone}
          onRefreshIntervalChange={setRefreshIntervalSec}
          onRefresh={loadAllData}
        />

        {/* Path-based Route Views */}
        <Routes>
          <Route path="/" element={<Navigate to="/overview" replace />} />
          <Route
            path="/overview"
            element={
              <OverviewView
                footfallData={footfallData}
                queueData={queueData}
                stockData={stockData}
                alertsData={alertsData}
              />
            }
          />
          <Route
            path="/camera"
            element={<CameraView isConnected={isConnected} debugMode={debugMode} />}
          />
          <Route
            path="/heatmap"
            element={<HeatmapView heatmapData={heatmapData} isLoading={isRefreshing} />}
          />
          <Route
            path="/queues"
            element={<QueuesView queueEvents={queueData} congestionThreshold={4} />}
          />
          <Route
            path="/inventory"
            element={<InventoryView stockEvents={stockData} />}
          />
          <Route
            path="/alerts"
            element={
              <AlertsView
                alerts={alertsData}
                activeFilter={alertFilter}
                onFilterChange={(st) => {
                  setAlertFilter(st);
                  loadAllData();
                }}
              />
            }
          />
          <Route
            path="/settings"
            element={
              <SettingsView
                debugMode={debugMode}
                envVariables={envVariables}
                onSave={() => loadAllData()}
              />
            }
          />
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Routes>
      </div>
    </div>
  );
}
