import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import { app } from 'electron';
import { loadSettings } from './settings';

let serverProcess: ChildProcess | null = null;
let serverPort: number | null = null;

function getBinaryPath(): string {
  const isDev = !app.isPackaged;

  if (isDev) {
    // Development: use the binary from backend/
    return path.join(app.getAppPath(), '..', 'backend', 'frfr-server');
  } else {
    // Production: use the bundled binary
    return path.join(process.resourcesPath, 'bin', 'frfr-server');
  }
}

function getWorkingPath(): string {
  // Use working path from settings (defaults to ~/Documents/frfr)
  const settings = loadSettings();
  return settings.workingPath;
}

async function waitForServer(port: number, timeoutMs: number = 30000): Promise<boolean> {
  const startTime = Date.now();
  const healthUrl = `http://127.0.0.1:${port}/api/health`;

  while (Date.now() - startTime < timeoutMs) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 1000);

      const response = await fetch(healthUrl, { signal: controller.signal });
      clearTimeout(timeout);

      if (response.ok) {
        console.log(`[backend] Server ready on port ${port}`);
        return true;
      }
    } catch {
      // Server not ready yet, continue polling
    }

    await new Promise(resolve => setTimeout(resolve, 100));
  }

  return false;
}

export async function startBackend(): Promise<number> {
  // Dynamic import for get-port (ESM module)
  const getPort = (await import('get-port')).default;
  const port = await getPort({ port: [8080, 8081, 8082, 8083, 8084, 8085] });

  const binaryPath = getBinaryPath();
  const workingPath = getWorkingPath();
  const sessionsPath = path.join(workingPath, 'sessions');
  const inputsPath = path.join(workingPath, 'inputs');

  console.log(`[backend] Binary path: ${binaryPath}`);
  console.log(`[backend] Working path: ${workingPath}`);
  console.log(`[backend] Starting on port: ${port}`);

  // Verify binary exists
  if (!fs.existsSync(binaryPath)) {
    throw new Error(`Backend binary not found at: ${binaryPath}`);
  }

  // Ensure directories exist
  if (!fs.existsSync(sessionsPath)) {
    fs.mkdirSync(sessionsPath, { recursive: true });
  }
  if (!fs.existsSync(inputsPath)) {
    fs.mkdirSync(inputsPath, { recursive: true });
  }

  // Get API key from settings if set
  const settings = loadSettings();
  const env: NodeJS.ProcessEnv = {
    ...process.env,
    FRFR_PORT: String(port),
    FRFR_DATA_DIR: sessionsPath,
    FRFR_INPUTS_DIR: inputsPath,
  };

  // Only set API key if user has configured one (not using native claude)
  if (settings.anthropicApiKey) {
    env.ANTHROPIC_API_KEY = settings.anthropicApiKey;
  }

  if (settings.fastMode) {
    env.FRFR_FAST_MODE = 'true';
  }

  serverProcess = spawn(binaryPath, [], {
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  serverProcess.stdout?.on('data', (data) => {
    console.log(`[backend] ${data.toString().trim()}`);
  });

  serverProcess.stderr?.on('data', (data) => {
    console.error(`[backend] ${data.toString().trim()}`);
  });

  serverProcess.on('error', (error) => {
    console.error('[backend] Failed to start:', error);
  });

  serverProcess.on('exit', (code, signal) => {
    console.log(`[backend] Exited with code ${code}, signal ${signal}`);
    serverProcess = null;
  });

  // Wait for server to be ready
  const ready = await waitForServer(port);
  if (!ready) {
    stopBackend();
    throw new Error('Backend server failed to start within timeout');
  }

  serverPort = port;
  return port;
}

export function stopBackend(): void {
  if (!serverProcess) {
    return;
  }

  console.log('[backend] Stopping server...');

  // Try graceful shutdown first
  serverProcess.kill('SIGTERM');

  // Force kill after timeout
  const killTimeout = setTimeout(() => {
    if (serverProcess) {
      console.log('[backend] Force killing server...');
      serverProcess.kill('SIGKILL');
    }
  }, 5000);

  serverProcess.once('exit', () => {
    clearTimeout(killTimeout);
    console.log('[backend] Server stopped');
  });

  serverProcess = null;
  serverPort = null;
}

export function getBackendPort(): number | null {
  return serverPort;
}

export function isBackendRunning(): boolean {
  return serverProcess !== null && serverPort !== null;
}

export async function restartBackend(): Promise<number> {
  console.log('[backend] Restarting server...');

  // Stop current server
  if (serverProcess) {
    serverProcess.kill('SIGTERM');

    // Wait for it to exit
    await new Promise<void>((resolve) => {
      if (!serverProcess) {
        resolve();
        return;
      }

      const timeout = setTimeout(() => {
        if (serverProcess) {
          serverProcess.kill('SIGKILL');
        }
        resolve();
      }, 3000);

      serverProcess.once('exit', () => {
        clearTimeout(timeout);
        resolve();
      });
    });

    serverProcess = null;
    serverPort = null;
  }

  // Start with new settings
  return startBackend();
}
