import { defineConfig } from '@playwright/test';
import development from './playwright.config';

export default defineConfig({
  ...development,
  // This target is the isolated acceptance Compose stack, never the user's app.
  use: { ...development.use, baseURL: 'http://127.0.0.1:4303' },
  webServer: [],
});
