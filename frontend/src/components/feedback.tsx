import { createContext, useCallback, useContext, useMemo, useRef, useState, type PropsWithChildren } from "react";
import { errorMessage } from "../services/api";
import { Button, Modal } from "./ui";

type Toast = { id: number; tone: "success" | "error"; text: string };
type ConfirmState = { title: string; body: string; confirmLabel: string; resolve: (ok: boolean) => void };
type Feedback = {
  success: (text: string) => void;
  error: (text: string) => void;
  confirm: (title: string, body: string, confirmLabel?: string) => Promise<boolean>;
  /** Run an async action; toast the error (and optional success message). Returns the result or undefined on failure. */
  run: <T>(fn: () => Promise<T>, successMessage?: string) => Promise<T | undefined>;
};

const Ctx = createContext<Feedback | null>(null);
export const useFeedback = () => { const c = useContext(Ctx); if (!c) throw new Error("FeedbackProvider missing"); return c; };

export function FeedbackProvider({ children }: PropsWithChildren) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [dialog, setDialog] = useState<ConfirmState | null>(null);
  const seq = useRef(0);

  const push = useCallback((tone: Toast["tone"], text: string) => {
    const id = ++seq.current;
    setToasts((t) => [...t.slice(-3), { id, tone, text }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), tone === "error" ? 7000 : 3500);
  }, []);

  const value = useMemo<Feedback>(() => ({
    success: (t) => push("success", t),
    error: (t) => push("error", t),
    confirm: (title, body, confirmLabel = "Delete") => new Promise<boolean>((resolve) => setDialog({ title, body, confirmLabel, resolve })),
    run: async (fn, successMessage) => {
      try { const result = await fn(); if (successMessage) push("success", successMessage); return result; }
      catch (e) { push("error", errorMessage(e)); return undefined; }
    }
  }), [push]);

  const close = (ok: boolean) => { dialog?.resolve(ok); setDialog(null); };

  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="toasts" aria-live="polite">
        {toasts.map((t) => <div key={t.id} className={`toast toast-${t.tone}`} role={t.tone === "error" ? "alert" : "status"}>{t.text}</div>)}
      </div>
      <Modal open={!!dialog} title={dialog?.title ?? ""} onClose={() => close(false)}>
        <p>{dialog?.body}</p>
        <div className="actions end">
          <Button variant="outline" onClick={() => close(false)}>Cancel</Button>
          <Button variant="danger" onClick={() => close(true)}>{dialog?.confirmLabel}</Button>
        </div>
      </Modal>
    </Ctx.Provider>
  );
}
