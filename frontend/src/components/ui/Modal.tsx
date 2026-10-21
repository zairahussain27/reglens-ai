import { useEffect, type PropsWithChildren } from "react";

export function Modal({ open, title, onClose, children }: PropsWithChildren<{ open: boolean; title: string; onClose: () => void }>) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div role="presentation" className="modal-backdrop" onClick={onClose}>
      <section role="dialog" aria-modal="true" aria-labelledby="modal-title" className="card" onClick={(e) => e.stopPropagation()}>
        <div className="row between">
          <h2 id="modal-title" style={{ margin: 0 }}>{title}</h2>
          <button type="button" className="icon-button" aria-label="Close dialog" onClick={onClose}>×</button>
        </div>
        {children}
      </section>
    </div>
  );
}
