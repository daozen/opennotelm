import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import {
  NavigationGuardProvider,
  useGuardedNavigation,
  useUnsavedChanges,
} from './NavigationGuard';

afterEach(() => vi.restoreAllMocks());

function Draft({ dirty, leave }: { dirty: boolean; leave: () => void }) {
  useUnsavedChanges(dirty);
  const navigate = useGuardedNavigation();
  return <button onClick={() => navigate(leave)}>Leave</button>;
}

it('keeps the draft on cancelled navigation and releases the guard after saving', () => {
  const leave = vi.fn();
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
  const view = render(
    <NavigationGuardProvider>
      <Draft dirty leave={leave} />
    </NavigationGuardProvider>,
  );
  fireEvent.click(screen.getByText('Leave'));
  expect(leave).not.toHaveBeenCalled();
  const event = new Event('beforeunload', { cancelable: true });
  window.dispatchEvent(event);
  expect(event.defaultPrevented).toBe(true);
  view.rerender(
    <NavigationGuardProvider>
      <Draft dirty={false} leave={leave} />
    </NavigationGuardProvider>,
  );
  fireEvent.click(screen.getByText('Leave'));
  expect(leave).toHaveBeenCalledOnce();
  expect(confirm).toHaveBeenCalledOnce();
  const savedEvent = new Event('beforeunload', { cancelable: true });
  window.dispatchEvent(savedEvent);
  expect(savedEvent.defaultPrevented).toBe(false);
});
