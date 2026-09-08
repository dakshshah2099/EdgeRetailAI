import React, { useState, useEffect } from 'react';
import { updateSystemEnv, toggleDebugMode } from '../lib/api.js';
import { Settings, Save, RotateCcw, Check, AlertCircle, Plus, Trash2 } from 'lucide-react';

export default function SettingsView({
  debugMode = false,
  envVariables = {},
  onSave,
}) {
  const [editVars, setEditVars] = useState({});
  const [isDirty, setIsDirty] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [isError, setIsError] = useState(false);
  const [newKey, setNewKey] = useState('');
  const [newVal, setNewVal] = useState('');

  useEffect(() => {
    if (!isDirty && envVariables) {
      setEditVars({ ...envVariables });
    }
  }, [envVariables, isDirty]);

  function handleInputChange(key, val) {
    setEditVars((prev) => ({ ...prev, [key]: val }));
    setIsDirty(true);
    setStatusMessage('');
  }

  function handleAddCustom() {
    if (!newKey.trim()) return;
    const formattedKey = newKey.trim().toUpperCase().replace(/[^A-Z0-9_]/g, '_');
    setEditVars((prev) => ({ ...prev, [formattedKey]: newVal }));
    setNewKey('');
    setNewVal('');
    setIsDirty(true);
  }

  function handleDeleteKey(key) {
    const updated = { ...editVars };
    delete updated[key];
    setEditVars(updated);
    setIsDirty(true);
  }

  function resetEdits() {
    setEditVars({ ...envVariables });
    setIsDirty(false);
    setStatusMessage('Changes reset to server configuration.');
    setIsError(false);
  }

  async function handleSave() {
    setIsSaving(true);
    setStatusMessage('');
    setIsError(false);
    try {
      const res = await updateSystemEnv(editVars);
      setStatusMessage('Configuration saved and written to edge .env successfully.');
      setIsError(false);
      setIsDirty(false);
      if (onSave) onSave(res);
    } catch (err) {
      setStatusMessage(`Failed to update config: ${err.message}`);
      setIsError(true);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="page-content">
      {/* Title Bar */}
      <div style={styles.titleBar}>
        <div>
          <h1>System & Edge Configuration</h1>
          <p>On-the-fly edge .env variables, camera source routing, and YOLO thresholds.</p>
        </div>

        <div style={styles.actionButtons}>
          <button
            onClick={resetEdits}
            disabled={!isDirty || isSaving}
            style={styles.resetBtn}
          >
            <RotateCcw size={14} />
            <span>Reset</span>
          </button>
          <button
            onClick={handleSave}
            disabled={!isDirty || isSaving}
            style={styles.saveBtn}
          >
            <Save size={14} />
            <span>{isSaving ? 'Saving...' : 'Save Changes'}</span>
          </button>
        </div>
      </div>

      {/* Status Notice */}
      {statusMessage && (
        <div
          style={{
            ...styles.statusBanner,
            backgroundColor: isError ? 'var(--status-danger-bg)' : 'var(--status-success-bg)',
            borderColor: isError ? 'var(--status-danger-border)' : 'var(--status-success-border)',
            color: isError ? 'var(--status-danger-text)' : 'var(--status-success-text)',
          }}
        >
          {isError ? <AlertCircle size={16} /> : <Check size={16} />}
          <span>{statusMessage}</span>
        </div>
      )}

      {/* Primary Configuration Form */}
      <div className="surface-card" style={styles.formCard}>
        <h2>Core Edge Parameters</h2>
        <div style={styles.formGrid}>
          {/* Camera Source */}
          <div style={styles.fieldGroup}>
            <label style={styles.label}>Camera Source (RTSP / Webcam / File)</label>
            <input
              type="text"
              value={editVars.CAMERA_SOURCE ?? ''}
              onChange={(e) => handleInputChange('CAMERA_SOURCE', e.target.value)}
              placeholder="e.g. rtsp://192.168.1.50:8554/live or 0"
              style={styles.input}
            />
            <div style={styles.presetRow}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-subtle)' }}>Presets:</span>
              <button
                type="button"
                onClick={() => handleInputChange('CAMERA_SOURCE', '0')}
                style={styles.presetBtn}
              >
                USB Webcam (0)
              </button>
              <button
                type="button"
                onClick={() => handleInputChange('CAMERA_SOURCE', 'tests/fixtures/sample_store.mp4')}
                style={styles.presetBtn}
              >
                Demo Video
              </button>
            </div>
          </div>

          {/* YOLO Detection Confidence */}
          <div style={styles.fieldGroup}>
            <label style={styles.label}>Detection Confidence Threshold (0.1 - 0.9)</label>
            <input
              type="number"
              step="0.05"
              min="0.05"
              max="0.95"
              value={editVars.DETECTION_CONF_THRESHOLD ?? '0.25'}
              onChange={(e) => handleInputChange('DETECTION_CONF_THRESHOLD', e.target.value)}
              style={styles.input}
            />
          </div>

          {/* Queue Congestion Threshold */}
          <div style={styles.fieldGroup}>
            <label style={styles.label}>Queue Congestion Threshold (Persons)</label>
            <input
              type="number"
              min="1"
              max="20"
              value={editVars.CONGESTION_THRESHOLD ?? '4'}
              onChange={(e) => handleInputChange('CONGESTION_THRESHOLD', e.target.value)}
              style={styles.input}
            />
          </div>

          {/* Log Level */}
          <div style={styles.fieldGroup}>
            <label style={styles.label}>Log Verbosity Level</label>
            <select
              value={editVars.LOG_LEVEL ?? 'INFO'}
              onChange={(e) => handleInputChange('LOG_LEVEL', e.target.value)}
              style={styles.input}
            >
              <option value="DEBUG">DEBUG (High Verbosity)</option>
              <option value="INFO">INFO (Production Standard)</option>
              <option value="WARNING">WARNING (Silent)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Advanced All Environment Variables Table */}
      <div className="surface-card">
        <h2>Environment Variable Audit</h2>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-subtle)', marginBottom: '1rem' }}>
          Direct key-value pairs stored in the edge node runtime.
        </p>

        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: '40%' }}>Variable Key</th>
                <th>Runtime Value</th>
                <th style={{ width: '60px' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(editVars).map(([k, v]) => (
                <tr key={k}>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', fontWeight: 600 }}>
                    {k}
                  </td>
                  <td>
                    <input
                      type="text"
                      value={String(v ?? '')}
                      onChange={(e) => handleInputChange(k, e.target.value)}
                      style={{ ...styles.input, padding: '0.25rem 0.5rem', width: '100%' }}
                    />
                  </td>
                  <td>
                    <button
                      onClick={() => handleDeleteKey(k)}
                      style={styles.deleteBtn}
                      title="Remove key"
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Add New Key Form */}
        <div style={styles.addRow}>
          <input
            type="text"
            placeholder="NEW_VARIABLE_NAME"
            value={newKey}
            onChange={(e) => setNewKey(e.target.value)}
            style={{ ...styles.input, flex: 1, fontFamily: 'var(--font-mono)' }}
          />
          <input
            type="text"
            placeholder="Value"
            value={newVal}
            onChange={(e) => setNewVal(e.target.value)}
            style={{ ...styles.input, flex: 1 }}
          />
          <button onClick={handleAddCustom} style={styles.addBtn}>
            <Plus size={14} />
            <span>Add Key</span>
          </button>
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
  actionButtons: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
  },
  resetBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.35rem',
    padding: '0.4rem 0.75rem',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border-subtle)',
    backgroundColor: 'var(--bg-surface)',
    color: 'var(--text-muted)',
    fontSize: '0.8rem',
    cursor: 'pointer',
  },
  saveBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.35rem',
    padding: '0.4rem 0.85rem',
    borderRadius: 'var(--radius-sm)',
    backgroundColor: 'var(--accent-primary)',
    color: '#ffffff',
    fontSize: '0.8rem',
    fontWeight: 600,
    cursor: 'pointer',
  },
  statusBanner: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    padding: '0.75rem 1rem',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid transparent',
    fontSize: '0.85rem',
    fontWeight: 500,
  },
  formCard: {
    display: 'flex',
    flexDirection: 'column',
    gap: '1.25rem',
  },
  formGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
    gap: '1.25rem',
  },
  fieldGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.4rem',
  },
  label: {
    fontSize: '0.8rem',
    fontWeight: 600,
    color: 'var(--text-main)',
  },
  input: {
    padding: '0.5rem 0.75rem',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border-subtle)',
    backgroundColor: 'var(--bg-surface)',
    color: 'var(--text-main)',
    fontSize: '0.85rem',
  },
  presetRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.4rem',
    marginTop: '0.2rem',
  },
  presetBtn: {
    padding: '0.2rem 0.5rem',
    borderRadius: 'var(--radius-sm)',
    backgroundColor: 'var(--bg-muted)',
    border: '1px solid var(--border-subtle)',
    fontSize: '0.725rem',
    color: 'var(--text-muted)',
    cursor: 'pointer',
  },
  deleteBtn: {
    padding: '0.3rem',
    color: '#dc2626',
    cursor: 'pointer',
    borderRadius: 'var(--radius-sm)',
  },
  addRow: {
    display: 'flex',
    gap: '0.75rem',
    marginTop: '1.25rem',
    paddingTop: '1.25rem',
    borderTop: '1px solid var(--border-subtle)',
  },
  addBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.35rem',
    padding: '0.5rem 0.85rem',
    borderRadius: 'var(--radius-sm)',
    backgroundColor: 'var(--bg-muted)',
    border: '1px solid var(--border-subtle)',
    color: 'var(--text-main)',
    fontWeight: 500,
    fontSize: '0.8rem',
    cursor: 'pointer',
  },
};
