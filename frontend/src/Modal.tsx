import { useEffect, useRef, type ReactNode } from 'react';

const openModals: HTMLElement[] = [];
const inertBackground = new Map<HTMLElement, { count: number; original: boolean }>();
let originalOverflow = '';
const selector = 'button, a[href], input, select, textarea, summary, [tabindex]';

/** Shared keyboard and scroll behavior for all modal dialogs, including nested citations. */
export default function Modal({
  children,
  onClose,
  busy = false,
}: {
  children: ReactNode;
  onClose: () => void;
  busy?: boolean;
}) {
  const backdrop = useRef<HTMLDivElement>(null);
  const previousFocus = useRef(document.activeElement);
  const state = useRef({ onClose, busy });
  state.current = { onClose, busy };
  useEffect(() => {
    const container = backdrop.current!;
    const dialog = container.querySelector<HTMLElement>('[role="dialog"]')!;
    if (!openModals.length) originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialog.tabIndex = -1;
    openModals.push(container);
    const topmost = () => openModals.at(-1) === container;
    const focusable = () =>
      [...dialog.querySelectorAll<HTMLElement>(selector)].filter(
        (el) =>
          !el.matches(':disabled, [tabindex="-1"]') &&
          !el.closest('[hidden], [inert]') &&
          getComputedStyle(el).display !== 'none' &&
          getComputedStyle(el).visibility !== 'hidden' &&
          !el.closest('details:not([open]) > :not(summary)'),
      );
    // Inert the background, walking ancestors so dialogs can remain next to their owning view.
    const background: HTMLElement[] = [];
    let branch: HTMLElement = container;
    while (branch.parentElement && branch.parentElement !== document.body) {
      for (const sibling of branch.parentElement.children) {
        if (sibling !== branch && sibling instanceof HTMLElement) {
          background.push(sibling);
          const lock = inertBackground.get(sibling) ?? {
            count: 0,
            original: Boolean(sibling.inert),
          };
          lock.count += 1;
          inertBackground.set(sibling, lock);
          sibling.inert = true;
        }
      }
      branch = branch.parentElement;
    }
    if (!dialog.contains(document.activeElement))
      (dialog.querySelector<HTMLElement>('[data-modal-focus]') ?? focusable()[0] ?? dialog).focus();
    const keydown = (event: KeyboardEvent) => {
      if (!topmost()) return;
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        if (!state.current.busy) state.current.onClose();
      }
      if (event.key === 'Tab') {
        const targets = focusable();
        const first = targets[0] ?? dialog;
        const last = targets.at(-1) ?? dialog;
        if (
          !targets.length ||
          !dialog.contains(document.activeElement) ||
          (event.shiftKey &&
            (document.activeElement === first || document.activeElement === dialog)) ||
          (!event.shiftKey && document.activeElement === last)
        ) {
          event.preventDefault();
          (event.shiftKey ? last : first).focus();
        }
      }
    };
    const containFocus = (event: FocusEvent) => {
      if (topmost() && event.target instanceof Node && !dialog.contains(event.target))
        (focusable()[0] ?? dialog).focus();
    };
    document.addEventListener('keydown', keydown);
    document.addEventListener('focusin', containFocus);
    return () => {
      document.removeEventListener('keydown', keydown);
      document.removeEventListener('focusin', containFocus);
      openModals.splice(openModals.indexOf(container), 1);
      for (const element of background) {
        const lock = inertBackground.get(element)!;
        lock.count -= 1;
        if (!lock.count) {
          element.inert = lock.original;
          inertBackground.delete(element);
        }
      }
      if (!openModals.length) document.body.style.overflow = originalOverflow;
      const previous = previousFocus.current;
      if (previous instanceof HTMLElement && previous.isConnected) previous.focus();
    };
  }, []);
  return (
    <div ref={backdrop} className="modal-backdrop">
      {children}
    </div>
  );
}
