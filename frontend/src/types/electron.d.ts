export interface ElectronAPI {
  isElectron: true;
  getBackendPort: () => Promise<number | null>;
  pickFiles: () => Promise<string[]>;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
