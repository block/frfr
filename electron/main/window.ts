import { BrowserWindow, app } from 'electron';
import * as path from 'path';

let mainWindow: BrowserWindow | null = null;

export function createWindow(backendPort: number): BrowserWindow {
  const isDev = !app.isPackaged;

  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    titleBarStyle: 'default',
    webPreferences: {
      preload: path.join(__dirname, '..', 'preload', 'index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  // Load the app with backend port in query string
  if (isDev) {
    // Development: load from Vite dev server
    const devUrl = `http://localhost:3000?backendPort=${backendPort}`;
    console.log(`[window] Loading dev URL: ${devUrl}`);
    mainWindow.loadURL(devUrl);

    // Open DevTools in development
    mainWindow.webContents.openDevTools();
  } else {
    // Production: load from bundled frontend
    const frontendPath = path.join(process.resourcesPath, 'frontend', 'index.html');
    console.log(`[window] Loading production path: ${frontendPath}`);
    mainWindow.loadFile(frontendPath, {
      query: { backendPort: String(backendPort) },
    });
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  return mainWindow;
}

export function getMainWindow(): BrowserWindow | null {
  return mainWindow;
}
