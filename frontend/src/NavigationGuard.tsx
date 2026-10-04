import { t, useI18n } from './i18n';
import { createContext, useCallback, useContext, useEffect, useRef, type ReactNode } from 'react';

type Guard = {
  register: (id: symbol) => () => void;
  navigate: (action: () => void) => boolean;
};
const Context = createContext<Guard | null>(null);

export function NavigationGuardProvider({ children }: { children: ReactNode }) {
  useI18n();
  const drafts = useRef(new Set<symbol>());
  const register = useCallback((id: symbol) => {
    drafts.current.add(id);
    return () => {
      drafts.current.delete(id);
    };
  }, []);
  const navigate = useCallback((action: () => void) => {
    if (drafts.current.size && !window.confirm(t('有未保存的修改。离开将丢弃这些修改，是否继续？')))
      return false;
    action();
    return true;
  }, []);
  useEffect(() => {
    const protect = (event: BeforeUnloadEvent) => {
      if (!drafts.current.size) return;
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', protect);
    return () => window.removeEventListener('beforeunload', protect);
  }, []);
  return <Context.Provider value={{ register, navigate }}>{children}</Context.Provider>;
}

export function useUnsavedChanges(dirty: boolean) {
  const guard = useContext(Context);
  const id = useRef(Symbol('draft'));
  useEffect(() => {
    if (dirty && guard) return guard.register(id.current);
  }, [dirty, guard?.register]);
}

export function useGuardedNavigation() {
  const guard = useContext(Context);
  return (
    guard?.navigate ??
    ((action: () => void) => {
      action();
      return true;
    })
  );
}
