export interface AppSettings {
  workingPath: string;
  anthropicApiKey: string;
  fastMode: boolean;
}

export interface ClaudeNativeStatus {
  available: boolean;
  loggedIn: boolean;
  error?: string;
}

export interface SettingsResponse {
  settings: AppSettings;
  defaultWorkingPath: string;
  claudeNative: ClaudeNativeStatus;
}

export interface SaveSettingsResponse {
  settings: AppSettings;
  restarted: boolean;
  newPort?: number;
}

export interface ElectronAPI {
  isElectron: true;
  getBackendPort: () => Promise<number | null>;
  pickFiles: () => Promise<string[]>;
  getSettings: () => Promise<SettingsResponse>;
  saveSettings: (settings: Partial<AppSettings>) => Promise<SaveSettingsResponse>;
  checkClaudeNative: () => Promise<ClaudeNativeStatus>;
  pickDirectory: () => Promise<string | null>;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
