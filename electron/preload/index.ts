import { contextBridge, ipcRenderer } from 'electron';

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
});
