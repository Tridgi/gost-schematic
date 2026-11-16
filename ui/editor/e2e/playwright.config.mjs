import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: '.',
  testMatch: '**/*.spec.mjs',
  timeout: 45000,
  expect: { timeout: 15000 },
  use: { ...devices['Desktop Chrome'], baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  reporter: [['list'], ['html', {open:'never', outputFolder:'playwright-report'}]],
  workers: 1,
  webServer: {
    command: 'npm run dev',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: false,
    timeout: 120000
  }
});
