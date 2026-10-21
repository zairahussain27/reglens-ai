import type { InputHTMLAttributes, PropsWithChildren, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";
export { Button } from "./Button";
export { Input } from "./Input";
export { Card } from "./Card";
export { Badge } from "./Badge";
export { Modal } from "./Modal";

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) { return <select className="control" {...props} />; }
export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) { return <textarea className="control" rows={3} {...props} />; }

export function FormField({ label, error, hint, children }: PropsWithChildren<{ label: ReactNode; error?: string; hint?: string }>) {
  return <label className="field"><span>{label}</span>{children}{hint && <small className="hint">{hint}</small>}{error && <span className="error">{error}</span>}</label>;
}

export function Checkbox({ label, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: ReactNode }) {
  return <label className="check"><input type="checkbox" {...props} /><span>{label}</span></label>;
}

export function Alert({ children, tone = "info" }: PropsWithChildren<{ tone?: "info" | "error" }>) {
  return <div className={`alert ${tone === "error" ? "alert-error" : ""}`} role={tone === "error" ? "alert" : "status"}>{children}</div>;
}

export function ErrorNotice({ error }: { error?: string }) { return error ? <Alert tone="error">{error}</Alert> : null; }

export function PageHeader({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="page-header">
      <div className="row between top">
        <div><h1>{title}</h1>{description && <p>{description}</p>}</div>
        {action}
      </div>
    </div>
  );
}

export function Loader() { return <div className="loader" role="status"><span className="spinner" />Loading…</div>; }
export function Page({ children }: PropsWithChildren) { return <main className="page">{children}</main>; }
export function Table({ children }: PropsWithChildren) { return <div className="table-wrap"><table>{children}</table></div>; }
export function Actions({ children }: PropsWithChildren) { return <div className="actions">{children}</div>; }
export function Empty({ children }: PropsWithChildren) { return <p className="empty">{children}</p>; }
export function Kpi({ value, label, hint }: { value: ReactNode; label: string; hint?: string }) {
  return <div className="kpi"><strong>{value}</strong><span>{label}</span>{hint && <small>{hint}</small>}</div>;
}
