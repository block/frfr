import { useState, useEffect } from 'react';
import type { AppSettings, ClaudeNativeStatus } from '../../types/electron';

interface Props {
  onClose: () => void;
}

function SettingsModal({ onClose }: Props) {
  const [settings, setSettings] = useState<AppSettings>({
    workingPath: '',
    anthropicApiKey: '',
    fastMode: false,
  });
  const [defaultPath, setDefaultPath] = useState('');
  const [claudeNative, setClaudeNative] = useState<ClaudeNativeStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  async function loadSettings() {
    if (!window.electronAPI) {
      setLoading(false);
      return;
    }

    try {
      const response = await window.electronAPI.getSettings();
      setSettings(response.settings);
      setDefaultPath(response.defaultWorkingPath);
      setClaudeNative(response.claudeNative);
    } catch (err) {
      console.error('Failed to load settings:', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    if (!window.electronAPI) return;

    setSaving(true);
    try {
      const result = await window.electronAPI.saveSettings(settings);

      if (result.restarted && result.newPort) {
        // Backend restarted with new settings - reload page with new port
        const url = new URL(window.location.href);
        url.searchParams.set('backendPort', String(result.newPort));
        window.location.href = url.toString();
      } else {
        onClose();
      }
    } catch (err) {
      console.error('Failed to save settings:', err);
    } finally {
      setSaving(false);
    }
  }

  async function handlePickDirectory() {
    if (!window.electronAPI) return;

    const dir = await window.electronAPI.pickDirectory();
    if (dir) {
      setSettings((s) => ({ ...s, workingPath: dir }));
    }
  }

  const isClaudeNativeAvailable = claudeNative?.available && claudeNative?.loggedIn;

  if (!window.electronAPI) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal" onClick={(e) => e.stopPropagation()}>
          <div className="modal-header">
            <h3 className="modal-title">Settings</h3>
            <button className="modal-close" onClick={onClose}>
              &times;
            </button>
          </div>
          <p className="text-muted">Settings are only available in the desktop app.</p>
          <div className="modal-footer">
            <button className="btn btn-primary" onClick={onClose}>
              Close
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">Settings</h3>
          <button className="modal-close" onClick={onClose}>
            &times;
          </button>
        </div>

        {loading ? (
          <div style={{ padding: '2rem 0', textAlign: 'center' }}>
            <span className="text-muted">Loading settings...</span>
          </div>
        ) : (
          <div style={{ paddingTop: '0.5rem' }}>
            {/* Working Directory */}
            <div className="form-group">
              <label className="form-label">Working Directory</label>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <input
                  type="text"
                  className="form-input"
                  value={settings.workingPath}
                  onChange={(e) =>
                    setSettings((s) => ({ ...s, workingPath: e.target.value }))
                  }
                  placeholder={defaultPath}
                />
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handlePickDirectory}
                  style={{ whiteSpace: 'nowrap' }}
                >
                  Browse...
                </button>
              </div>
              <p
                className="text-xs text-muted"
                style={{ marginTop: '0.375rem' }}
              >
                Contains sessions/ and inputs/ folders. Default: {defaultPath}
              </p>
            </div>

            {/* Anthropic API Key */}
            <div className="form-group">
              <label className="form-label">Anthropic API Key</label>
              {isClaudeNativeAvailable ? (
                <>
                  <input
                    type="password"
                    className="form-input"
                    value="configured-via-claude-cli"
                    disabled
                    style={{
                      backgroundColor: 'var(--color-bg)',
                      color: 'var(--color-text-muted)',
                      cursor: 'not-allowed',
                    }}
                  />
                  <p
                    className="text-xs"
                    style={{
                      marginTop: '0.375rem',
                      color: 'var(--color-success)',
                    }}
                  >
                    Claude is configured through native login (claude CLI)
                  </p>
                </>
              ) : (
                <>
                  <input
                    type="password"
                    className="form-input"
                    value={settings.anthropicApiKey}
                    onChange={(e) =>
                      setSettings((s) => ({ ...s, anthropicApiKey: e.target.value }))
                    }
                    placeholder="sk-ant-..."
                  />
                  <p
                    className="text-xs text-muted"
                    style={{ marginTop: '0.375rem' }}
                  >
                    Your Anthropic API key for Claude access
                  </p>
                </>
              )}
            </div>

            {/* Model Speed */}
            <div className="form-group">
              <label className="form-label">Model</label>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.75rem',
                }}
              >
                <button
                  type="button"
                  onClick={() =>
                    setSettings((s) => ({ ...s, fastMode: !s.fastMode }))
                  }
                  style={{
                    position: 'relative',
                    width: '44px',
                    height: '24px',
                    borderRadius: '12px',
                    border: 'none',
                    backgroundColor: settings.fastMode
                      ? 'var(--color-primary)'
                      : 'var(--color-border)',
                    cursor: 'pointer',
                    transition: 'background-color 0.2s',
                    padding: 0,
                    flexShrink: 0,
                  }}
                >
                  <span
                    style={{
                      position: 'absolute',
                      top: '2px',
                      left: settings.fastMode ? '22px' : '2px',
                      width: '20px',
                      height: '20px',
                      borderRadius: '50%',
                      backgroundColor: 'white',
                      transition: 'left 0.2s',
                    }}
                  />
                </button>
                <span style={{ fontSize: '0.875rem' }}>
                  {settings.fastMode ? 'Fast' : 'Normal'}
                </span>
                <span
                  className="text-xs text-muted"
                  style={{ marginLeft: 'auto' }}
                >
                  claude-opus-4-6
                </span>
              </div>
              <p
                className="text-xs text-muted"
                style={{ marginTop: '0.375rem' }}
              >
                {settings.fastMode
                  ? isClaudeNativeAvailable && !settings.anthropicApiKey
                    ? 'Requires an API key — not supported with native CLI auth'
                    : 'Same fidelity, faster output (higher cost)'
                  : 'Standard speed (default)'}
              </p>
            </div>
          </div>
        )}

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={handleSave}
            disabled={loading || saving}
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default SettingsModal;
