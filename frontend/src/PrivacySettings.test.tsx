import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import PrivacySettings from './PrivacySettings';

describe('Privacy settings', () => {
  it('saves consent without a receiver, persists after reopening, and allows disabling', async () => {
    let enabled = false;
    const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, init) => {
      if (String(url).endsWith('/preferences')) {
        enabled = JSON.parse(String(init?.body)).telemetry_enabled;
        return new Response(JSON.stringify({ telemetry_enabled: enabled, ui_language: 'zh-CN' }));
      }
      return new Response(JSON.stringify({ enabled, configured: false, queued_events: 0 }));
    });
    const first = render(<PrivacySettings />);
    const toggle = screen.getByRole('checkbox', { name: '允许匿名使用统计' });
    await waitFor(() => expect(toggle).toBeEnabled());
    expect(toggle).not.toBeChecked();
    expect(screen.getByText(/勾选后仅在本地暂存匿名统计/)).toBeInTheDocument();
    fireEvent.click(toggle);
    await screen.findByText('统计偏好已保存。');
    expect(toggle).toBeChecked();
    expect(enabled).toBe(true);
    // Successful PUT is the authoritative response; no fallible follow-up GET.
    expect(fetch.mock.calls.filter(([url]) => String(url).endsWith('/telemetry'))).toHaveLength(1);
    first.unmount();
    render(<PrivacySettings />);
    const reopened = screen.getByRole('checkbox', { name: '允许匿名使用统计' });
    await waitFor(() => expect(reopened).toBeChecked());
    fireEvent.click(reopened);
    await screen.findByText('统计偏好已保存。');
    expect(reopened).not.toBeChecked();
    expect(enabled).toBe(false);
  });

  it('rolls back a failed save and allows retry', async () => {
    let fail = true;
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      if (String(url).endsWith('/preferences')) {
        return fail
          ? new Response(JSON.stringify({ error: { code: 'NETWORK_ERROR' } }), { status: 502 })
          : new Response(JSON.stringify({ telemetry_enabled: true }));
      }
      return new Response(JSON.stringify({ enabled: false, configured: true, queued_events: 0 }));
    });
    render(<PrivacySettings />);
    const toggle = screen.getByRole('checkbox', { name: '允许匿名使用统计' });
    await waitFor(() => expect(toggle).toBeEnabled());
    fireEvent.click(toggle);
    await screen.findByRole('alert');
    expect(toggle).not.toBeChecked();
    expect(toggle).toBeEnabled();
    fail = false;
    fireEvent.click(toggle);
    await screen.findByText('统计偏好已保存。');
    expect(toggle).toBeChecked();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
