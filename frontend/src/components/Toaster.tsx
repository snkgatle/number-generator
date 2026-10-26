import React, { createContext, useContext, useCallback, useState } from 'react';

export type ToastVariant = 'success' | 'error' | 'warning' | 'info';

interface Toast {
  id: string;
  variant: ToastVariant;
  title: string;
  message?: string;
}

interface ToasterContextValue {
  toast: (variant: ToastVariant, title: string, message?: string) => void;
  dismiss: (id: string) => void;
}

const ToasterCtx = createContext<ToasterContextValue>({
  toast: () => {},
  dismiss: () => {},
});

export function useToast() {
  return useContext(ToasterCtx);
}

export const ToasterProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback((variant: ToastVariant, title: string, message?: string) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
    setToasts((prev) => [...prev, { id, variant, title, message }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000);
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToasterCtx.Provider value={{ toast, dismiss }}>
      {children}
      {/* Render toasts outside document flow */}
      <div className="fixed right-4 top-20 z-50 flex flex-col gap-2 max-w-sm pointer-events-none">
        {toasts.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => dismiss(t.id)}
            className={`pointer-events-auto rounded-md border px-3.5 py-2.5 shadow-lg transition-all duration-200 animate-slide-in-right flex items-start gap-2.5 text-sm ${
              t.variant === 'success'
                ? 'border-emerald-500/30 bg-emerald-500/[0.10] text-emerald-200'
                : t.variant === 'error'
                  ? 'border-rose-500/30 bg-rose-500/[0.10] text-rose-200'
                  : t.variant === 'warning'
                    ? 'border-amber-500/30 bg-amber-500/[0.10] text-amber-200'
                    : 'border-line bg-surface-1 text-zinc-300'
            }`}
            role="alert"
            aria-live="polite"
          >
            <span className="flex-1">
              <span className="font-semibold">{t.title}</span>
              {t.message && <p className="mt-0.5 text-xs opacity-80">{t.message}</p>}
            </span>
            <span className="text-xs opacity-50 ml-2 shrink-0">×</span>
          </button>
        ))}
      </div>
    </ToasterCtx.Provider>
  );
};
