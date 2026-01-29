import { ipcMain, dialog } from 'electron';
import { getMainWindow } from './window';
import { getBackendPort } from './backend';

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
}
