import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',

  use: {
    /* Vite dev server proxies /api to the backend. */
    baseURL: 'http://localhost:5003',
    trace: 'on-first-retry',
  },

  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' },
    },
  ],

  /* In CI, start both backend and frontend. Locally, reuse existing servers. */
  webServer: [
    {
      command: 'cd ../backend && uvicorn main:app --port 5002',
      url: 'http://localhost:5002/health',
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      command: 'npm run dev',
      url: 'http://localhost:5003',
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
  ],
})
