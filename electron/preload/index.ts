import { contextBridge, ipcRenderer } from 'electron';

// Types for settings
interface AppSettings {
  workingPath: string;
  anthropicApiKey: string;
  fastMode: boolean;
}

interface ClaudeNativeStatus {
  available: boolean;
  loggedIn: boolean;
  error?: string;
}

interface SettingsResponse {
  settings: AppSettings;
  defaultWorkingPath: string;
  claudeNative: ClaudeNativeStatus;
}

interface SaveSettingsResponse {
  settings: AppSettings;
  restarted: boolean;
  newPort?: number;
}

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // Flag to detect Electron environment
  isElectron: true,

  // Get the backend port
  getBackendPort: (): Promise<number | null> => {
    return ipcRenderer.invoke('get-backend-port');
  },

  // Pick files using native dialog
  pickFiles: (): Promise<string[]> => {
    return ipcRenderer.invoke('pick-files');
  },

  // Settings
  getSettings: (): Promise<SettingsResponse> => {
    return ipcRenderer.invoke('get-settings');
  },

  saveSettings: (settings: Partial<AppSettings>): Promise<SaveSettingsResponse> => {
    return ipcRenderer.invoke('save-settings', settings);
  },

  checkClaudeNative: (): Promise<ClaudeNativeStatus> => {
    return ipcRenderer.invoke('check-claude-native');
  },

  // Pick directory for session path
  pickDirectory: (): Promise<string | null> => {
    return ipcRenderer.invoke('pick-directory');
  },
});
