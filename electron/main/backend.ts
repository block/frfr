import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import { app } from 'electron';

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

function getDataPath(): string {
  // Use app's userData directory for the database
  return app.getPath('userData');
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
  const dataPath = getDataPath();

  console.log(`[backend] Binary path: ${binaryPath}`);
  console.log(`[backend] Data path: ${dataPath}`);
  console.log(`[backend] Starting on port: ${port}`);

  // Verify binary exists
  if (!fs.existsSync(binaryPath)) {
    throw new Error(`Backend binary not found at: ${binaryPath}`);
  }

  // Ensure data directory exists
  if (!fs.existsSync(dataPath)) {
    fs.mkdirSync(dataPath, { recursive: true });
  }

  serverProcess = spawn(binaryPath, [], {
    env: {
      ...process.env,
      FRFR_PORT: String(port),
      FRFR_DATA_DIR: dataPath,
    },
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
