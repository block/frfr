import { ipcMain, dialog } from 'electron';
import { getMainWindow } from './window';
import { getBackendPort, restartBackend } from './backend';
import {
  loadSettings,
  saveSettings,
  getDefaultWorkingPath,
  checkClaudeNative,
  type AppSettings,
} from './settings';

export function setupIPC(): void {
  // Get backend port
  ipcMain.handle('get-backend-port', () => {
    return getBackendPort();
  });

  // File picker using Electron's native dialog
  ipcMain.handle('pick-files', async () => {
    const mainWindow = getMainWindow();
    if (!mainWindow) {
      return [];
    }

    const result = await dialog.showOpenDialog(mainWindow, {
      title: 'Select PDF Documents',
      properties: ['openFile', 'multiSelections'],
      filters: [
        { name: 'PDF Documents', extensions: ['pdf'] },
        { name: 'All Files', extensions: ['*'] },
      ],
    });

    if (result.canceled) {
      return [];
    }

    return result.filePaths;
  });

  // Settings
  ipcMain.handle('get-settings', () => {
    const settings = loadSettings();
    const claudeStatus = checkClaudeNative();
    return {
      settings,
      defaultWorkingPath: getDefaultWorkingPath(),
      claudeNative: claudeStatus,
    };
  });

  ipcMain.handle('save-settings', async (_event, newSettings: Partial<AppSettings>) => {
    const oldSettings = loadSettings();
    const saved = saveSettings(newSettings);

    // Check if we need to restart the backend
    const needsRestart =
      newSettings.workingPath !== undefined && newSettings.workingPath !== oldSettings.workingPath ||
      newSettings.anthropicApiKey !== undefined && newSettings.anthropicApiKey !== oldSettings.anthropicApiKey;

    if (needsRestart) {
      const newPort = await restartBackend();
      return { settings: saved, restarted: true, newPort };
    }

    return { settings: saved, restarted: false };
  });

  ipcMain.handle('check-claude-native', () => {
    return checkClaudeNative();
  });

  // Directory picker for working path
  ipcMain.handle('pick-directory', async () => {
    const mainWindow = getMainWindow();
    if (!mainWindow) {
      return null;
    }

    const result = await dialog.showOpenDialog(mainWindow, {
      title: 'Select Working Directory',
      properties: ['openDirectory', 'createDirectory'],
    });

    if (result.canceled || result.filePaths.length === 0) {
      return null;
    }

    return result.filePaths[0];
  });
}
