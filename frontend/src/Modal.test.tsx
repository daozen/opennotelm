import { fireEvent, render, screen } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import Modal from './Modal';

function Example({ close, busy = false }: { close: () => void; busy?: boolean }) {
  return (
    <Modal onClose={close} busy={busy}>
      <section role="dialog" aria-modal="true" aria-label="Example">
        <button>First</button>
        <input aria-label="Draft" />
        <button>Last</button>
      </section>
    </Modal>
  );
}

test('dialogs contain keyboard focus, close on Escape, and restore the original focus and scroll state', () => {
  const trigger = document.createElement('button');
  document.body.append(trigger);
  trigger.focus();
  const close = vi.fn();
  const { unmount } = render(<Example close={close} />);
  expect(screen.getByText('First')).toHaveFocus();
  expect(document.body.style.overflow).toBe('hidden');
  screen.getByText('Last').focus();
  fireEvent.keyDown(document, { key: 'Tab' });
  expect(screen.getByText('First')).toHaveFocus();
  fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
  expect(screen.getByText('Last')).toHaveFocus();
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(close).toHaveBeenCalledOnce();
  unmount();
  expect(document.body.style.overflow).toBe('');
  expect(trigger).toHaveFocus();
  trigger.remove();
});

test('only the top nested dialog handles Escape and in-flight operations cannot be dismissed', () => {
  const parent = vi.fn();
  const child = vi.fn();
  render(<Example close={parent} />);
  const { rerender, unmount } = render(<Example close={child} busy />);
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(child).not.toHaveBeenCalled();
  expect(parent).not.toHaveBeenCalled();
  rerender(<Example close={child} />);
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(child).toHaveBeenCalledOnce();
  expect(parent).not.toHaveBeenCalled();
  unmount();
  expect(document.body.style.overflow).toBe('hidden');
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(parent).toHaveBeenCalledOnce();
});
