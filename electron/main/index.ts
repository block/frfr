import { app, BrowserWindow } from 'electron';
import { startBackend, stopBackend } from './backend';
import { createWindow } from './window';
import { setupIPC } from './ipc';
import { initClaudeStatus } from './settings';

let isQuitting = false;

async function initialize(): Promise<void> {
  console.log('[app] Initializing...');

  try {
    // Pre-check Claude status (cached for instant access later)
    initClaudeStatus();

    // Setup IPC handlers before creating window
    setupIPC();

    // Start the Go backend
    console.log('[app] Starting backend...');
    const port = await startBackend();
    console.log(`[app] Backend started on port ${port}`);

    // Create the main window
    createWindow(port);

    console.log('[app] Initialization complete');
  } catch (error) {
    console.error('[app] Failed to initialize:', error);
    app.quit();
  }
}

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
app.whenReady().then(initialize);

// Quit when all windows are closed.
app.on('window-all-closed', () => {
  // On macOS, apps typically stay active until explicitly quit
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', async () => {
  // On macOS, re-create a window when dock icon is clicked
  if (BrowserWindow.getAllWindows().length === 0) {
    try {
      const { getBackendPort, isBackendRunning } = await import('./backend');

      if (isBackendRunning()) {
        const port = getBackendPort();
        if (port) {
          createWindow(port);
        }
      } else {
        // Backend stopped, restart everything
        await initialize();
      }
    } catch (error) {
      console.error('[app] Failed to reactivate:', error);
    }
  }
});

// Clean up before quit
app.on('before-quit', () => {
  isQuitting = true;
});

app.on('will-quit', (event) => {
  if (!isQuitting) {
    return;
  }

  console.log('[app] Shutting down...');
  stopBackend();
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  console.error('[app] Uncaught exception:', error);
  stopBackend();
  app.quit();
});

process.on('unhandledRejection', (reason) => {
  console.error('[app] Unhandled rejection:', reason);
});
