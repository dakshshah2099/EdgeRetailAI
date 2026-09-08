import React, { useState, useEffect, useRef } from 'react';
import { fetchSystemZones, updateSystemZones } from '../lib/api.js';
import {
  Video,
  Layers,
  Crosshair,
  Maximize,
  Minimize,
  RefreshCw,
  Edit3,
  Check,
  X,
  AlertCircle,
} from 'lucide-react';

export default function CameraView({ isConnected = true, debugMode = false }) {
  const [overlayZones, setOverlayZones] = useState(true);
  const [overlayDetections, setOverlayDetections] = useState(true);
  const [targetFps, setTargetFps] = useState(15);
  const [streamTimestamp, setStreamTimestamp] = useState(Date.now());
  const [isStreamLoading, setIsStreamLoading] = useState(true);
  const [isStreamError, setIsStreamError] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Visual Zone Calibration
  const [isEditingZones, setIsEditingZones] = useState(false);
  const [zones, setZones] = useState([]);
  const [selectedZoneIdx, setSelectedZoneIdx] = useState(0);
  const [activeDragHandle, setActiveDragHandle] = useState(null);
  const [isSavingZones, setIsSavingZones] = useState(false);
  const [zoneStatusMsg, setZoneStatusMsg] = useState('');
  const [isZoneError, setIsZoneError] = useState(false);

  const containerRef = useRef(null);

  const streamUrl = `/video/stream?overlay_zones=${!isEditingZones && overlayZones}&overlay_detections=${overlayDetections}&fps=${targetFps}&t=${streamTimestamp}`;

  useEffect(() => {
    loadZones();
  }, []);

  async function loadZones() {
    try {
      const z = await fetchSystemZones();
      setZones(z || []);
    } catch (err) {
      console.error('Failed to load zones:', err);
    }
  }

  function refreshStream() {
    setIsStreamLoading(true);
    setIsStreamError(false);
    setStreamTimestamp(Date.now());
  }

  function toggleFullscreen() {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().catch((err) => console.error(err));
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  }

  async function saveZones() {
    setIsSavingZones(true);
    setZoneStatusMsg('');
    try {
      await updateSystemZones(zones);
      setZoneStatusMsg('Zones successfully saved to edge config!');
      setIsZoneError(false);
      setTimeout(() => {
        setIsEditingZones(false);
        setZoneStatusMsg('');
        refreshStream();
      }, 1200);
    } catch (err) {
      setZoneStatusMsg(err.message || 'Failed to save zones');
      setIsZoneError(true);
    } finally {
      setIsSavingZones(false);
    }
  }

  // Handle Dragging Polygon Point
  function handleSvgPointerDown(zoneIdx, ptIdx, e) {
    e.preventDefault();
    setActiveDragHandle({ zoneIdx, ptIdx });
  }

  function handleSvgPointerMove(e) {
    if (!activeDragHandle || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const y = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));

    const updated = [...zones];
    updated[activeDragHandle.zoneIdx].polygon[activeDragHandle.ptIdx] = [
      Math.round(x * 1000) / 1000,
      Math.round(y * 1000) / 1000,
    ];
    setZones(updated);
  }

  function handleSvgPointerUp() {
    setActiveDragHandle(null);
  }

  return (
    <div className="page-content">
      {/* Title & Stream Controls */}
      <div style={styles.titleBar}>
        <div>
          <h1>Live Edge Vision</h1>
          <p>Real-time YOLOv8 person tracking & spatial polygon calibration.</p>
        </div>

        {/* Toolbar */}
        <div style={styles.toolbar}>
          <button
            onClick={() => setOverlayDetections(!overlayDetections)}
            style={{
              ...styles.toolBtn,
              ...(overlayDetections ? styles.toolBtnActive : {}),
            }}
            title="Toggle YOLO Bounding Boxes"
          >
            <Crosshair size={15} />
            <span>Boxes</span>
          </button>

          <button
            onClick={() => setOverlayZones(!overlayZones)}
            style={{
              ...styles.toolBtn,
              ...(overlayZones ? styles.toolBtnActive : {}),
            }}
            title="Toggle Zone Polygons"
          >
            <Layers size={15} />
            <span>Zones</span>
          </button>

          <button
            onClick={() => setIsEditingZones(!isEditingZones)}
            style={{
              ...styles.toolBtn,
              ...(isEditingZones ? styles.toolBtnEditActive : {}),
            }}
            title="Calibrate ROI Polygon Coordinates"
          >
            <Edit3 size={15} />
            <span>{isEditingZones ? 'Exit Calibration' : 'Calibrate Zones'}</span>
          </button>

          <button
            onClick={refreshStream}
            style={styles.toolBtn}
            title="Reconnect Video Stream"
          >
            <RefreshCw size={15} />
          </button>

          <button
            onClick={toggleFullscreen}
            style={styles.toolBtn}
            title="Fullscreen"
          >
            {isFullscreen ? <Minimize size={15} /> : <Maximize size={15} />}
          </button>
        </div>
      </div>

      {/* Main Video Viewport Card */}
      <div className="surface-card" style={styles.videoCard}>
        <div
          ref={containerRef}
          style={styles.videoContainer}
          onPointerMove={handleSvgPointerMove}
          onPointerUp={handleSvgPointerUp}
        >
          {/* Live MJPEG Stream Image */}
          <img
            src={streamUrl}
            alt="Live Edge Camera Stream"
            style={styles.videoStream}
            onLoad={() => {
              setIsStreamLoading(false);
              setIsStreamError(false);
            }}
            onError={() => {
              setIsStreamLoading(false);
              setIsStreamError(true);
            }}
          />

          {/* Loading Indicator */}
          {isStreamLoading && (
            <div style={styles.overlayCenter}>
              <RefreshCw size={24} style={styles.spin} />
              <span style={{ fontSize: '0.85rem', marginTop: '0.5rem' }}>
                Connecting to edge camera pipeline...
              </span>
            </div>
          )}

          {/* Error Indicator */}
          {isStreamError && (
            <div style={styles.overlayCenter}>
              <AlertCircle size={28} color="#ef4444" />
              <span style={{ fontSize: '0.9rem', fontWeight: 600, marginTop: '0.5rem' }}>
                Camera Stream Offline
              </span>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-subtle)', marginTop: '0.25rem' }}>
                Verify camera RTSP URL or USB device in Settings.
              </p>
              <button onClick={refreshStream} style={styles.retryBtn}>
                Retry Connection
              </button>
            </div>
          )}

          {/* Interactive Calibration Overlay SVG */}
          {isEditingZones && (
            <svg
              style={styles.svgOverlay}
              viewBox="0 0 1000 1000"
              preserveAspectRatio="none"
            >
              {zones.map((zone, zIdx) => {
                const isSelected = zIdx === selectedZoneIdx;
                const ptsStr = zone.polygon
                  .map((p) => `${p[0] * 1000},${p[1] * 1000}`)
                  .join(' ');

                return (
                  <g key={zone.zone_id}>
                    {/* Polygon fill & stroke */}
                    <polygon
                      points={ptsStr}
                      fill={isSelected ? 'rgba(37, 99, 235, 0.25)' : 'rgba(100, 116, 139, 0.15)'}
                      stroke={isSelected ? '#2563eb' : '#64748b'}
                      strokeWidth={isSelected ? '3' : '1.5'}
                      strokeDasharray={isSelected ? 'none' : '6 4'}
                      style={{ cursor: 'pointer' }}
                      onClick={() => setSelectedZoneIdx(zIdx)}
                    />

                    {/* Draggable Vertex Handles */}
                    {isSelected &&
                      zone.polygon.map((p, pIdx) => (
                        <circle
                          key={pIdx}
                          cx={p[0] * 1000}
                          cy={p[1] * 1000}
                          r="12"
                          fill="#ffffff"
                          stroke="#2563eb"
                          strokeWidth="3"
                          style={{ cursor: 'grab' }}
                          onPointerDown={(e) => handleSvgPointerDown(zIdx, pIdx, e)}
                        />
                      ))}
                  </g>
                );
              })}
            </svg>
          )}
        </div>

        {/* Calibration Controls Footer */}
        {isEditingZones && (
          <div style={styles.editBar}>
            <div style={styles.editZoneTabs}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                Active Zone:
              </span>
              {zones.map((z, idx) => (
                <button
                  key={z.zone_id}
                  onClick={() => setSelectedZoneIdx(idx)}
                  style={{
                    ...styles.zoneTabBtn,
                    ...(idx === selectedZoneIdx ? styles.zoneTabBtnActive : {}),
                  }}
                >
                  {z.name || z.zone_id}
                </button>
              ))}
            </div>

            <div style={styles.editActions}>
              {zoneStatusMsg && (
                <span
                  style={{
                    fontSize: '0.8rem',
                    fontWeight: 500,
                    color: isZoneError ? '#dc2626' : '#059669',
                  }}
                >
                  {zoneStatusMsg}
                </span>
              )}
              <button
                onClick={saveZones}
                disabled={isSavingZones}
                style={styles.saveBtn}
              >
                <Check size={14} />
                <span>{isSavingZones ? 'Saving...' : 'Save Coordinates'}</span>
              </button>
              <button
                onClick={() => setIsEditingZones(false)}
                style={styles.cancelBtn}
              >
                <X size={14} />
                <span>Close</span>
              </button>
            </div>
          </div>
        )}
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
  toolbar: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.4rem',
  },
  toolBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.35rem',
    padding: '0.4rem 0.65rem',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border-subtle)',
    backgroundColor: 'var(--bg-surface)',
    color: 'var(--text-muted)',
    fontSize: '0.8rem',
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  toolBtnActive: {
    backgroundColor: 'var(--accent-primary-subtle)',
    color: 'var(--accent-primary-text)',
    borderColor: '#93c5fd',
  },
  toolBtnEditActive: {
    backgroundColor: '#fffbeb',
    color: '#b45309',
    borderColor: '#fde68a',
    fontWeight: 600,
  },
  videoCard: {
    padding: 0,
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: '#0f172a',
  },
  videoContainer: {
    position: 'relative',
    width: '100%',
    aspectRatio: '16/9',
    backgroundColor: '#090d16',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  videoStream: {
    width: '100%',
    height: '100%',
    objectFit: 'contain',
    display: 'block',
  },
  svgOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    pointerEvents: 'auto',
  },
  overlayCenter: {
    position: 'absolute',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#f8fafc',
    backgroundColor: 'rgba(15, 23, 42, 0.75)',
    padding: '2rem',
    borderRadius: 'var(--radius-md)',
  },
  retryBtn: {
    marginTop: '0.75rem',
    padding: '0.35rem 0.75rem',
    borderRadius: 'var(--radius-sm)',
    backgroundColor: '#2563eb',
    color: '#ffffff',
    fontSize: '0.8rem',
    fontWeight: 500,
    cursor: 'pointer',
  },
  spin: {
    animation: 'spin 1.5s linear infinite',
  },
  editBar: {
    padding: '0.75rem 1.25rem',
    backgroundColor: 'var(--bg-surface)',
    borderTop: '1px solid var(--border-subtle)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '1rem',
  },
  editZoneTabs: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
  },
  zoneTabBtn: {
    padding: '0.3rem 0.6rem',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border-subtle)',
    backgroundColor: 'var(--bg-muted)',
    color: 'var(--text-muted)',
    fontSize: '0.775rem',
    cursor: 'pointer',
  },
  zoneTabBtnActive: {
    backgroundColor: 'var(--accent-primary)',
    color: '#ffffff',
    borderColor: 'var(--accent-primary)',
    fontWeight: 600,
  },
  editActions: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
  },
  saveBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.35rem',
    padding: '0.35rem 0.75rem',
    borderRadius: 'var(--radius-sm)',
    backgroundColor: '#059669',
    color: '#ffffff',
    fontSize: '0.8rem',
    fontWeight: 600,
    cursor: 'pointer',
  },
  cancelBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.35rem',
    padding: '0.35rem 0.65rem',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border-subtle)',
    backgroundColor: 'var(--bg-surface)',
    color: 'var(--text-muted)',
    fontSize: '0.8rem',
    cursor: 'pointer',
  },
};
