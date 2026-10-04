import '@testing-library/jest-dom/vitest';
import { afterEach, beforeEach, vi } from 'vitest';
import { applyLanguage } from './i18n';
import { cleanup } from '@testing-library/react';

Object.defineProperty(Element.prototype, 'scrollIntoView', {
  value: vi.fn(),
  configurable: true,
  writable: true,
});

beforeEach(async () => {
  await applyLanguage('zh-CN');
  localStorage.clear();
});

afterEach(async () => {
  cleanup();
  await applyLanguage('zh-CN');
  localStorage.clear();
  vi.restoreAllMocks();
});
