import { defineConfig } from '@playwright/test';

const shellQuote = (value: string) => `'${value.replaceAll("'", "'\\''")}'`;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:4302',
    trace: 'retain-on-failure',
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? {
          executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
        }
      : {},
  },
  webServer: [
    {
      // Child npm processes may resolve an older ancestor Node binary. Use the
      // runtime already running Playwright for the Vite server as well.
      command: `OPENNOTELM_API_PROXY=http://127.0.0.1:4300 ${shellQuote(process.execPath)} node_modules/vite/bin/vite.js --host 127.0.0.1 --port 4302 --strictPort`,
      url: 'http://127.0.0.1:4302',
      reuseExistingServer: false,
    },
    {
      command:
        'DATA_DIR=../.e2e-data ../.venv/bin/uvicorn opennotelm.main:app --app-dir ../backend --host 127.0.0.1 --port 4300',
      url: 'http://127.0.0.1:4300/api/health',
      env: {
        RENDER_BROWSER_EXECUTABLE: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? '',
        TELEMETRY_HOST: 'http://127.0.0.1:4301',
        TELEMETRY_PROJECT_TOKEN: 'test-only-telemetry-token',
      },
      reuseExistingServer: false,
    },
    {
      command:
        '../.venv/bin/uvicorn mock_provider:app --app-dir ../backend/tests --host 127.0.0.1 --port 4301',
      url: 'http://127.0.0.1:4301/v1/models',
      reuseExistingServer: false,
    },
  ],
});
