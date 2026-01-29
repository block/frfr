import * as fs from 'fs';
import * as path from 'path';
import { app } from 'electron';
import { execSync } from 'child_process';

export interface AppSettings {
  workingPath: string;
  anthropicApiKey: string;
}

const DEFAULT_WORKING_PATH = path.join(
  process.env.HOME || '',
  'Documents',
  'frfr'
);

function getSettingsPath(): string {
  return path.join(app.getPath('userData'), 'settings.json');
}

function getDefaultSettings(): AppSettings {
  return {
    workingPath: DEFAULT_WORKING_PATH,
    anthropicApiKey: '',
  };
}

export function getDefaultWorkingPath(): string {
  return DEFAULT_WORKING_PATH;
}

export function loadSettings(): AppSettings {
  const settingsPath = getSettingsPath();
  const defaults = getDefaultSettings();

  try {
    if (fs.existsSync(settingsPath)) {
      const data = fs.readFileSync(settingsPath, 'utf-8');
      const saved = JSON.parse(data);
      return { ...defaults, ...saved };
    }
  } catch (error) {
    console.error('[settings] Failed to load settings:', error);
  }

  return defaults;
}

export function saveSettings(settings: Partial<AppSettings>): AppSettings {
  const settingsPath = getSettingsPath();
  const current = loadSettings();
  const updated = { ...current, ...settings };

  try {
    const dir = path.dirname(settingsPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(settingsPath, JSON.stringify(updated, null, 2));
  } catch (error) {
    console.error('[settings] Failed to save settings:', error);
  }

  return updated;
}


export interface ClaudeNativeStatus {
  available: boolean;
  loggedIn: boolean;
  error?: string;
}

// Cached Claude status (checked once at startup)
let cachedClaudeStatus: ClaudeNativeStatus | null = null;

export function checkClaudeNative(): ClaudeNativeStatus {
  // Return cached result if available
  if (cachedClaudeStatus !== null) {
    return cachedClaudeStatus;
  }

  try {
    // Check if claude CLI exists
    execSync('which claude', { encoding: 'utf-8', stdio: 'pipe' });
  } catch {
    cachedClaudeStatus = { available: false, loggedIn: false, error: 'Claude CLI not found' };
    return cachedClaudeStatus;
  }

  try {
    // Check if logged in by running claude status
    const output = execSync('claude status', {
      encoding: 'utf-8',
      stdio: 'pipe',
      timeout: 5000,
    });

    // If the output contains account info, user is logged in
    const loggedIn = output.includes('Logged in') ||
                     output.includes('account') ||
                     !output.includes('not logged in');

    cachedClaudeStatus = { available: true, loggedIn };
    return cachedClaudeStatus;
  } catch (error) {
    // claude status might fail if not logged in
    cachedClaudeStatus = { available: true, loggedIn: false };
    return cachedClaudeStatus;
  }
}

// Pre-check Claude status at startup (call this early in app init)
export function initClaudeStatus(): void {
  checkClaudeNative();
}
